from elasticsearch import Elasticsearch, exceptions
import os
import time
from flask import Flask, jsonify, request, render_template, make_response
import sys
import requests

es = Elasticsearch(host='es')

app = Flask(__name__)


def load_data_in_es():
    """ creates an index in elasticsearch """
    url = "http://data.sfgov.org/resource/rqzj-sfat.json"
    r = requests.get(url)
    data = r.json()
    print("Loading data in elasticsearch ...")
    for id, truck in enumerate(data):
        res = es.index(index="sfdata", doc_type="truck", id=id, body=truck)
    print("Total trucks loaded: ", len(data))


def safe_check_index(index, retry=1, max_retry=6):
    """ connect to ES with retry """
    if retry > max_retry:
        print("Out of retries. Bailing out...")
        sys.exit(1)
    try:
        status = es.indices.exists(index=index)
        return status
    except exceptions.ConnectionError as e:
        print(f'Unable to connect to ES. Retrying in {2**retry}s with exponential backoff...')
        time.sleep(2**retry)
        safe_check_index(index, retry+1)


def format_fooditems(string):
    items = [x.strip().lower() for x in string.split(":")]
    return items[1:] if items[0].find("cold truck") > -1 else items


def check_and_load_index():
    """ checks if index exits and loads the data accordingly """
    if not safe_check_index('sfdata'):
        print("Index not found...")
        load_data_in_es()



@app.route('/')
def index():
    return render_template('index.html')


@app.route('/debug')
def test_es():
    resp = {}
    try:
        msg = es.cat.indices()
        resp["msg"] = msg
        resp["status"] = "success"
    except:
        resp["status"] = "failure"
        resp["msg"] = "Unable to reach ES"
    return jsonify(resp)


@app.route('/search')
def search():
    key = request.args.get('q')
    if not key:
        return jsonify({
            "status": "failure",
            "msg": "Please provide a query"
        })
    try:
        res = es.search(
            index="sfdata",
            body={
                "query": {"match": {"fooditems": key}},
                "size": 750
            },
            request_timeout=5)
    except Exception as e:
        return make_response(
            jsonify({
                "status": "failure",
                "msg": "error in reaching elasticsearch"
            }),
            500
        )
    
    vendors = set([x["_source"]["applicant"] for x in res["hits"]["hits"]])
    temp = {v: [] for v in vendors}
    fooditems = {v: "" for v in vendors}
    
    for r in res["hits"]["hits"]:
        source = r["_source"]
        applicant = source["applicant"]
        
        if "location" not in source:
            continue
            
        location_data = source["location"]
        
        
        if isinstance(location_data, dict) and "latitude" in location_data and "longitude" in location_data:
            # Convert to coordinates array [longitude, latitude] format for Mapbox
            coordinates = [
                float(location_data["longitude"]),
                float(location_data["latitude"])
            ]
            
            truck = {
                "hours": source.get("dayshours", "NA"),
                "schedule": source.get("schedule", "NA"),
                "address": source.get("address", "NA"),
                "location": {
                    "coordinates": coordinates
                }
            }
            fooditems[applicant] = source["fooditems"]
            temp[applicant].append(truck)

    results = {"trucks": []}
    for v in temp:
        if temp[v]:
            results["trucks"].append({
                "name": v,
                "fooditems": format_fooditems(fooditems[v]),
                "branches": temp[v],
                "drinks": fooditems[v].find("COLD TRUCK") > -1
            })
    
    hits = len(results["trucks"])
    locations = sum([len(r["branches"]) for r in results["trucks"]])

    return jsonify({
        "trucks": results["trucks"],
        "hits": hits,
        "locations": locations,
        "status": "success"
    })

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/menu')
def menu():
    try:
        res = es.search(
            index="sfdata",
            body={
                "query": {"match_all": {}},
                "size": 1000,
                "_source": ["fooditems"]
            }
        )
        
        food_counter = {}
        
        for hit in res["hits"]["hits"]:
            
            fooditems_str = hit["_source"].get("fooditems", "")
            
            if fooditems_str:
                # Splitting logic
                item_list = [item.strip() for item in fooditems_str.replace(':', ',').split(',')]
                
                for food_item in item_list:
                    if food_item and len(food_item) > 2:
                        item_lower = food_item.lower()
                        food_counter[item_lower] = food_counter.get(item_lower, 0) + 1
        
        
        sorted_food_items = sorted(food_counter.items(), key=lambda x: x[1], reverse=True)
        top_food_items = sorted_food_items[:20]
        
        menu_items = []
        for food_name, food_count in top_food_items:
            menu_items.append({
                "name": food_name.title(),
                "count": food_count,
                "trucks": food_count
            })
        
        result = {
            "status": "success",
            "total_unique_items": len(food_counter),
            "showing": len(menu_items),
            "menu_list": menu_items
        }
        
        if request.args.get('format') == 'json':
            return jsonify(result)
            
        return render_template('menu.html', data=result)
        
    except Exception as e:

        error_data = {
            "status": "failure",
            "msg": "Unable to retrieve menu items",
            "error": str(e)
        }
        
        if request.args.get('format') == 'json':
            return jsonify(error_data), 500
            
        return render_template('menu.html', data=error_data, error=True), 500

@app.route('/health')
def health():
    """Health check endpoint - always returns JSON"""
    try:
        es.cluster.health()
        status_data = {
            "status": "healthy",
            "service": "SF Food Trucks API",
            "elasticsearch": "connected"
        }
        return jsonify(status_data), 200

    except:
        status_data = {
            "status": "unhealthy",
            "service": "SF Food Trucks API",
            "elasticsearch": "disconnected"
        }
        return jsonify(status_data), 503

@app.route('/stats')
def stats():
    """Get application statistics - supports both HTML and JSON"""
    try:
        res = es.search(
            index="sfdata",
            body={
                "query": {"match_all": {}},
                "size": 0,
                "aggs": {
                    "unique_trucks": {
                        "cardinality": {
                            "field": "applicant.keyword"
                        }
                    },
                    "total_locations": {
                        "value_count": {
                            "field": "location"
                        }
                    }
                }
            }
        )
        
        unique_trucks = res["aggregations"]["unique_trucks"]["value"]
        total_locations = res["aggregations"]["total_locations"]["value"]
        
        stats_data = {
            "status": "success",
            "total_trucks": unique_trucks,
            "total_locations": total_locations,
            "index": "sfdata"
        }
        
        if request.args.get('format') == 'json':
            return jsonify(stats_data)
            
        return render_template('stats.html', data=stats_data)
    except Exception as e:
        error_data = {
            "status": "failure",
            "msg": "Unable to retrieve stats",
            "error": str(e)
        }
        
        if request.args.get('format') == 'json':
            return jsonify(error_data), 500
            
        return render_template('stats.html', data=error_data, error=True), 500

@app.route('/random')
def random_truck():
    """Get a random food truck - supports both HTML and JSON"""
    try:
        res = es.search(
            index="sfdata",
            body={
                "query": {
                    "function_score": {
                        "query": {"match_all": {}},
                        "random_score": {}
                    }
                },
                "size": 1
            }
        )
        
        if res["hits"]["total"] == 0:
            error_data = {
                "status": "failure",
                "msg": "No trucks found"
            }
            
            if request.args.get('format') == 'json':
                return jsonify(error_data)
                
            return render_template('random.html', data=error_data, error=True)
        
        truck_data = res["hits"]["hits"][0]["_source"]
        
        result = {
            "status": "success",
            "truck": {
                "name": truck_data.get("applicant", "Unknown"),
                "fooditems": format_fooditems(truck_data.get("fooditems", "")),
                "address": truck_data.get("address", "NA"),
                "location": truck_data.get("location", {}),
                "hours": truck_data.get("dayshours", "NA"),
                "schedule": truck_data.get("schedule", "NA")
            }
        }
        
        if request.args.get('format') == 'json':
            return jsonify(result)
            
        return render_template('random.html', data=result)
    except Exception as e:
        error_data = {
            "status": "failure",
            "msg": "Unable to get random truck",
            "error": str(e)
        }
        
        if request.args.get('format') == 'json':
            return jsonify(error_data), 500
            
        return render_template('random.html', data=error_data, error=True), 500

@app.route('/filter')
def filter_trucks():
    """Filter trucks by cuisine type - supports both HTML and JSON"""
    cuisine = request.args.get('cuisine')
    
    if not cuisine:
        error_data = {
            "status": "failure",
            "msg": "Please provide a cuisine parameter"
        }
        
        if request.args.get('format') == 'json':
            return jsonify(error_data), 400
            
        return render_template('filter.html', data=error_data, error=True), 400
    
    try:
        res = es.search(
            index="sfdata",
            body={
                "query": {"match": {"fooditems": cuisine}},
                "size": 100
            }
        )
        
        vendors = set([x["_source"]["applicant"] for x in res["hits"]["hits"]])
        temp = {v: [] for v in vendors}
        fooditems_map = {v: "" for v in vendors}
        
        for r in res["hits"]["hits"]:
            applicant = r["_source"]["applicant"]
            if "location" in r["_source"]:
                truck = {
                    "hours": r["_source"].get("dayshours", "NA"),
                    "address": r["_source"].get("address", "NA"),
                    "location": r["_source"]["location"]
                }
                fooditems_map[applicant] = r["_source"]["fooditems"]
                temp[applicant].append(truck)
        
        results = []
        for v in temp:
            results.append({
                "name": v,
                "fooditems": format_fooditems(fooditems_map[v]),
                "branches": temp[v]
            })
        
        filter_data = {
            "status": "success",
            "cuisine": cuisine,
            "trucks": results,
            "count": len(results)
        }
        
        if request.args.get('format') == 'json':
            return jsonify(filter_data)
            
        return render_template('filter.html', data=filter_data)
    except Exception as e:
        error_data = {
            "status": "failure",
            "msg": "Unable to filter trucks",
            "error": str(e)
        }
        
        if request.args.get('format') == 'json':
            return jsonify(error_data), 500
            
        return render_template('filter.html', data=error_data, error=True), 500

if __name__ == "__main__":
    ENVIRONMENT_DEBUG = os.environ.get("DEBUG", False)
    check_and_load_index()
    app.run(host='0.0.0.0', port=5000, debug=ENVIRONMENT_DEBUG)
