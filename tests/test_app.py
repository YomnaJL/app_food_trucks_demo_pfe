import pytest
from unittest.mock import patch, MagicMock
import requests
import sys
import time
from flask_app.app import load_data_in_es, safe_check_index, format_fooditems, check_and_load_index, index, search, about, menu, health, stats, random_truck, filter_trucks

@pytest.fixture
def client():
    from flask_app.app import app
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c

def test_load_data_in_es_nonempty(monkeypatch, capsys):
    from flask_app.app import load_data_in_es, es, requests

    # Prepare fake data
    fake_data = [{"name": "truck1"}, {"name": "truck2"}]

    # Mock requests.get to return an object whose json() returns fake_data
    class DummyResponse:
        def json(self):
            return fake_data

    dummy_resp = DummyResponse()
    dummy_get = lambda url: dummy_resp
    monkeypatch.setattr(requests, "get", dummy_get)

    # Mock Elasticsearch object's index method
    indexed_calls = []

    class DummyES:
        def index(self, index, doc_type, id, body):
            indexed_calls.append((index, doc_type, id, body))

    dummy_es = DummyES()
    monkeypatch.setattr("flask_app.app.es", dummy_es)

    # Run the function
    load_data_in_es()

    # Verify requests.get was called with the correct URL
    # (the dummy_get lambda ignores its argument, so we just trust it was used)

    # Verify that index was called for each item with correct parameters
    assert indexed_calls == [
        ("sfdata", "truck", 0, {"name": "truck1"}),
        ("sfdata", "truck", 1, {"name": "truck2"}),
    ]

    # Verify printed output
    captured = capsys.readouterr().out
    assert "Loading data in elasticsearch ..." in captured
    assert "Total trucks loaded:  2" in captured

def test_load_data_in_es_empty(monkeypatch, capsys):
    from flask_app.app import load_data_in_es, es, requests

    # Prepare empty fake data
    fake_data = []

    class DummyResponse:
        def json(self):
            return fake_data

    dummy_resp = DummyResponse()
    monkeypatch.setattr(requests, "get", lambda url: dummy_resp)

    indexed_calls = []

    class DummyES:
        def index(self, *args, **kwargs):
            indexed_calls.append((args, kwargs))

    dummy_es = DummyES()
    monkeypatch.setattr("flask_app.app.es", dummy_es)

    # Run the function
    load_data_in_es()

    # No calls to index should have been made
    assert indexed_calls == []

    # Verify printed output mentions zero trucks
    captured = capsys.readouterr().out
    assert "Loading data in elasticsearch ..." in captured
    assert "Total trucks loaded:  0" in captured

@patch('flask_app.app.time')
@patch('flask_app.app.es')
def test_safe_check_index_happy_path_returns_exists(mock_es, mock_time):
    # Arrange: indices.exists returns True
    mock_es.indices.exists.return_value = True

    # Act
    from flask_app.app import safe_check_index
    result = safe_check_index('test-index')

    # Assert
    assert result is True
    # ensure no sleep was called
    mock_time.sleep.assert_not_called()
    # ensure indices.exists was called once with correct argument
    mock_es.indices.exists.assert_called_once_with(index='test-index')

@patch('flask_app.app.time')
@patch('flask_app.app.es')
@patch('flask_app.app.sys')
def test_safe_check_index_exceeds_max_retry_exits(mock_sys, mock_es, mock_time):
    # Arrange: always raise ConnectionError so retry loop continues
    from elasticsearch import exceptions
    mock_es.indices.exists.side_effect = exceptions.ConnectionError('always fail')
    # sys.exit should raise SystemExit when called
    mock_sys.exit.side_effect = SystemExit

    # Act & Assert
    from flask_app.app import safe_check_index
    with pytest.raises(SystemExit):
        safe_check_index('max-retry-index', retry=7, max_retry=6)

    # Ensure that after exceeding max_retry, sys.exit was invoked
    mock_sys.exit.assert_called_once()
    # No sleep should be called because the function exits before the retry block
    mock_time.sleep.assert_not_called()

def test_format_fooditems_basic_split():
    from flask_app.app import format_fooditems
    result = format_fooditems("Tacos: beef, chicken")
    assert result == ["tacos", "beef, chicken"]

def test_format_fooditems_cold_truck_prefix():
    from flask_app.app import format_fooditems
    result = format_fooditems("COLD TRUCK: ice cream, soda")
    # "cold truck" should be removed, returning only the items after the colon
    assert result == ["ice cream, soda"]

def test_format_fooditems_multiple_colons():
    from flask_app.app import format_fooditems
    result = format_fooditems("Cold Truck: coffee: latte")
    # First element contains "cold truck", so it is dropped; remaining parts stay in order
    assert result == ["coffee", "latte"]

def test_format_fooditems_no_colon():
    from flask_app.app import format_fooditems
    result = format_fooditems("Hot Dog")
    # No colon, function should return the single lowered element
    assert result == ["hot dog"]

def test_format_fooditems_cold_truck_inside_first_token():
    from flask_app.app import format_fooditems
    result = format_fooditems("some cold truck: item")
    # "cold truck" appears within the first token, so it is considered a match
    assert result == ["item"]

@patch('flask_app.app.load_data_in_es')
@patch('flask_app.app.safe_check_index')
def test_check_and_load_index_no_load_when_index_exists(mock_safe_check_index, mock_load_data_in_es):
    # Simulate that the index already exists
    mock_safe_check_index.return_value = True

    from flask_app import app as app_module
    app_module.check_and_load_index()

    # load_data_in_es should not be called because the index exists
    mock_load_data_in_es.assert_not_called()

@patch('flask_app.app.load_data_in_es')
@patch('flask_app.app.safe_check_index')
def test_check_and_load_index_loads_when_index_missing(mock_safe_check_index, mock_load_data_in_es):
    # Simulate that the index does not exist
    mock_safe_check_index.return_value = False

    from flask_app import app as app_module
    app_module.check_and_load_index()

    # load_data_in_es should be called to populate the missing index
    mock_load_data_in_es.assert_called_once()

def test_index_success(client):
    response = client.get("/")
    assert response.status_code == 200

@patch('flask_app.app.es')
def test_test_es_success(mock_es, client):
    # Simulate a successful call to Elasticsearch cat.indices
    mock_es.cat.indices.return_value = 'green 1 2 3'
    response = client.get('/debug')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert data['msg'] == 'green 1 2 3'

@patch('flask_app.app.es')
def test_test_es_failure(mock_es, client):
    # Simulate an exception raised by Elasticsearch cat.indices
    mock_es.cat.indices.side_effect = Exception('boom')
    response = client.get('/debug')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'failure'
    assert data['msg'] == 'Unable to reach ES'

@patch('flask_app.app.es')
def test_search_missing_query(mock_es, client):
    response = client.get('/search')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'failure'
    assert data['msg'] == 'Please provide a query'

@patch('flask_app.app.es')
def test_search_es_error(mock_es, client):
    mock_es.search.side_effect = Exception('boom')
    response = client.get('/search?q=test')
    assert response.status_code == 500
    data = response.get_json()
    assert data['status'] == 'failure'
    assert data['msg'] == 'error in reaching elasticsearch'

@patch('flask_app.app.es')
def test_search_success(mock_es, client):
    mock_es.search.return_value = {
        "hits": {
            "hits": [
                {
                    "_source": {
                        "applicant": "Vendor A",
                        "fooditems": "COLD TRUCK: tacos, burritos",
                        "location": {
                            "latitude": 37.0,
                            "longitude": -122.0
                        },
                        "dayshours": "9am-5pm",
                        "schedule": "Mon-Fri",
                        "address": "123 Main St"
                    }
                }
            ]
        }
    }

    response = client.get('/search?q=tacos')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert data['hits'] == 1
    assert data['locations'] == 1

    truck = data['trucks'][0]
    assert truck['name'] == 'Vendor A'
    assert truck['fooditems'] == ['tacos, burritos']
    assert truck['drinks'] is True
    assert len(truck['branches']) == 1

    branch = truck['branches'][0]
    assert branch['address'] == '123 Main St'
    assert branch['hours'] == '9am-5pm'
    assert branch['schedule'] == 'Mon-Fri'
    assert branch['location'] == {'coordinates': [-122.0, 37.0]}

def test_about_route_success(client):
    response = client.get('/about')
    assert response.status_code == 200
    # The response should be HTML content
    assert response.headers["Content-Type"].startswith("text/html")

@patch('flask_app.app.es')
def test_menu_success_json(mock_es, client):
    # Simulate Elasticsearch search returning a set of food items
    mock_es.search.return_value = {
        "hits": {
            "hits": [
                {"_source": {"fooditems": "Taco: Burger, Fries"}},
                {"_source": {"fooditems": "Burger, Pizza"}},
                {"_source": {"fooditems": "taco, burger"}}
            ]
        }
    }
    response = client.get('/menu?format=json')
    assert response.status_code == 200
    data = response.get_json()
    # Expected counts after processing
    expected_counter = {
        "burger": 3,
        "taco": 2,
        "fries": 1,
        "pizza": 1
    }
    # Verify summary fields
    assert data["status"] == "success"
    assert data["total_unique_items"] == len(expected_counter)
    assert data["showing"] == len(expected_counter)
    # Verify each menu item
    for item in data["menu_list"]:
        name_lower = item["name"].lower()
        assert name_lower in expected_counter
        assert item["count"] == expected_counter[name_lower]
        assert item["trucks"] == expected_counter[name_lower]

@patch('flask_app.app.es')
def test_menu_error_json(mock_es, client):
    # Simulate an exception raised during Elasticsearch search
    mock_es.search.side_effect = Exception('elasticsearch failure')
    response = client.get('/menu?format=json')
    assert response.status_code == 500
    data = response.get_json()
    assert data["status"] == "failure"
    assert data["msg"] == "Unable to retrieve menu items"
    assert "elasticsearch failure" in data["error"]

@patch('flask_app.app.es')
def test_health_success(mock_es, client):
    # Simulate successful Elasticsearch health check
    mock_es.cluster.health.return_value = {"status": "green"}

    # Retrieve the view function registered for the '/health' route
    health_view = client.application.view_functions['health']

    # Call the view function inside a request context
    with client.application.test_request_context('/health'):
        response, status_code = health_view()

    assert status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "healthy"
    assert json_data["elasticsearch"] == "connected"
    assert json_data["service"] == "SF Food Trucks API"

@patch('flask_app.app.es')
def test_health_failure(mock_es, client):
    # Simulate Elasticsearch raising an exception during health check
    mock_es.cluster.health.side_effect = Exception("connection error")

    health_view = client.application.view_functions['health']

    with client.application.test_request_context('/health'):
        response, status_code = health_view()

    assert status_code == 503
    json_data = response.get_json()
    assert json_data["status"] == "unhealthy"
    assert json_data["elasticsearch"] == "disconnected"
    assert json_data["service"] == "SF Food Trucks API"

@patch('flask_app.app.es')
def test_stats_success_json(mock_es, client):
    mock_es.search.return_value = {
        "aggregations": {
            "unique_trucks": {"value": 42},
            "total_locations": {"value": 100}
        }
    }
    response = client.get("/stats?format=json")
    assert response.status_code == 200
    data = response.get_json()
    assert data == {
        "status": "success",
        "total_trucks": 42,
        "total_locations": 100,
        "index": "sfdata"
    }

@patch('flask_app.app.es')
def test_stats_error_json(mock_es, client):
    mock_es.search.side_effect = Exception("elasticsearch down")
    response = client.get("/stats?format=json")
    assert response.status_code == 500
    data = response.get_json()
    assert data["status"] == "failure"
    assert data["msg"] == "Unable to retrieve stats"
    assert "elasticsearch down" in data["error"]

@patch('flask_app.app.es')
def test_random_truck_success_json(mock_es, client):
    mock_es.search.return_value = {
        "hits": {
            "total": 1,
            "hits": [
                {
                    "_source": {
                        "applicant": "Test Truck",
                        "fooditems": "Tacos: Burritos",
                        "address": "123 Street",
                        "location": {"latitude": "37.77", "longitude": "-122.41"},
                        "dayshours": "Mon-Fri 10-5",
                        "schedule": "Weekdays"
                    }
                }
            ]
        }
    }
    response = client.get("/random?format=json")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    truck = data["truck"]
    assert truck["name"] == "Test Truck"
    assert truck["address"] == "123 Street"
    assert truck["location"] == {"latitude": "37.77", "longitude": "-122.41"}
    assert truck["hours"] == "Mon-Fri 10-5"
    assert truck["schedule"] == "Weekdays"
    # format_fooditems lower‑cases and splits on ":"
    assert truck["fooditems"] == ["tacos", "burritos"]

@patch('flask_app.app.es')
def test_random_truck_no_trucks_json(mock_es, client):
    mock_es.search.return_value = {"hits": {"total": 0, "hits": []}}
    response = client.get("/random?format=json")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "failure"
    assert data["msg"] == "No trucks found"

@patch('flask_app.app.es')
def test_random_truck_exception_json(mock_es, client):
    mock_es.search.side_effect = Exception("boom")
    response = client.get("/random?format=json")
    assert response.status_code == 500
    data = response.get_json()
    assert data["status"] == "failure"
    assert data["msg"] == "Unable to get random truck"
    assert "error" in data

@patch('flask_app.app.es')
def test_filter_trucks_success(mock_es, client):
    # Mock Elasticsearch response with a single truck that has location data
    mock_es.search.return_value = {
        "hits": {
            "hits": [
                {
                    "_source": {
                        "applicant": "Truck1",
                        "location": {"latitude": 37.0, "longitude": -122.0},
                        "dayshours": "9-5",
                        "address": "123 Main St",
                        "fooditems": "Tacos: Beef, Lettuce"
                    }
                }
            ]
        }
    }

    response = client.get("/filter?cuisine=Tacos&format=json")
    assert response.status_code == 200
    data = response.get_json()

    # Basic response shape
    assert data["status"] == "success"
    assert data["cuisine"] == "Tacos"
    assert isinstance(data["trucks"], list)
    assert data["count"] == len(data["trucks"])

    # Verify the single truck entry
    truck = data["trucks"][0]
    assert truck["name"] == "Truck1"
    # format_fooditems lower‑cases and splits on ':'
    assert truck["fooditems"] == ["tacos", "beef, lettuce"]
    # branches should contain the location dict unchanged
    assert isinstance(truck["branches"], list) and len(truck["branches"]) == 1
    branch = truck["branches"][0]
    assert branch["hours"] == "9-5"
    assert branch["address"] == "123 Main St"
    assert branch["location"] == {"latitude": 37.0, "longitude": -122.0}

@patch('flask_app.app.es')
def test_filter_trucks_es_exception(mock_es, client):
    # Simulate an Elasticsearch failure
    mock_es.search.side_effect = Exception("elasticsearch down")
    response = client.get("/filter?cuisine=Pizza&format=json")
    assert response.status_code == 500
    data = response.get_json()
    assert data["status"] == "failure"
    assert "Unable to filter trucks" in data["msg"]

@patch('flask_app.app.es')
def test_filter_trucks_missing_cuisine(mock_es, client):
    response = client.get("/filter?format=json")
    assert response.status_code == 400
    data = response.get_json()
    assert isinstance(data, dict)
    assert data["status"] == "failure"
    assert data["msg"] == "Please provide a cuisine parameter"
