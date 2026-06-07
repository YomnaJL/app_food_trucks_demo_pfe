import React from 'react';
    import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import Sidebar from '../../../../flask_app/static/src/components/Sidebar';

jest.mock('superagent', () => ({
  get: jest.fn().mockReturnValue({
    set:   jest.fn().mockReturnThis(),
    query: jest.fn().mockReturnThis(),
    send:  jest.fn().mockReturnThis(),
    end:   jest.fn().mockImplementation((cb) => cb(null, { body: {} })),
  }),
  post: jest.fn().mockReturnValue({
    send:  jest.fn().mockReturnThis(),
    end:   jest.fn().mockImplementation((cb) => cb(null, { body: {} })),
  }),
}));
jest.mock('../../../../flask_app/static/src/components/Intro', () => () => null);
jest.mock('../../../../flask_app/static/src/components/Vendor', () => () => null);

// React class component — do NOT inline methods.
// Access methods via: const ref = React.createRef(); render(<Component ref={ref} />); ref.current.method();

describe('Sidebar.fetchResults', () => {
  let mockEnd;

  beforeEach(() => {
    jest.clearAllMocks();
    mockEnd = jest.fn();

    // mock superagent
    const request = require('superagent');
    request.get.mockReturnValue({ end: mockEnd });
  });

  it('updates the DOM with results after a successful fetch', async () => {
    const responseBody = {
      hits: 2,
      locations: 1,
      trucks: [
        {
          name: 'TacoTruck',
          branches: [
            {
              location: { latitude: '10', longitude: '20' },
              schedule: '9-5',
              hours: '9-5',
              address: '123 Main St',
            },
          ],
        },
      ],
    };

    mockEnd.mockImplementationOnce((cb) => cb(null, { body: responseBody }));

    const ref = React.createRef();
    render(<Sidebar ref={ref} map={{}} />);

    // avoid running the heavy map logic
    jest.spyOn(ref.current, 'plotOnMap').mockImplementation(() => {});

    // type a query
    fireEvent.change(
      screen.getByPlaceholderText(/Burgers, Tacos or Wraps\?/i),
      { target: { value: 'taco' } }
    );

    // submit the form
    fireEvent.submit(screen.getByRole('button', { name: /Search!/i }));

    const request = require('superagent');
    expect(request.get).toHaveBeenCalledWith('/search?q=taco');

    // heading appears after async state update
    const heading = await screen.findByRole('heading', { level: 5 });
    expect(heading).toBeInTheDocument();

    // counts are rendered inside the spans
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('shows an alert when the fetch fails', async () => {
    global.alert = jest.fn();

    mockEnd.mockImplementationOnce((cb) => cb(new Error('network error'), null));

    const ref = React.createRef();
    render(<Sidebar ref={ref} map={{}} />);

    fireEvent.change(
      screen.getByPlaceholderText(/Burgers, Tacos or Wraps\?/i),
      { target: { value: 'breakfast' } }
    );
    fireEvent.submit(screen.getByRole('button', { name: /Search!/i }));

    await screen.findByRole('button', { name: /Search!/i }); // wait for async cycle

    expect(global.alert).toHaveBeenCalledWith('error in fetching response');
  });
});

describe('Sidebar.generateGeoJSON', () => {
  let ref;
  const mockMap = {
    getLayer: jest.fn(),
    removeLayer: jest.fn(),
    getSource: jest.fn(),
    removeSource: jest.fn(),
    addSource: jest.fn().mockReturnThis(),
    addLayer: jest.fn().mockReturnThis(),
  };

  beforeEach(() => {
    ref = React.createRef();
    render(<Sidebar ref={ref} map={mockMap} />);
  });

  it('returns a FeatureCollection with correct features for given markers', () => {
    const markers = [
      {
        name: 'Vendor A',
        hours: '9-5',
        address: '123 Main St',
        location: { latitude: '10.0', longitude: '20.0' },
      },
      {
        name: 'Vendor B',
        hours: '10-6',
        address: '456 Oak Ave',
        location: { latitude: '30.5', longitude: '40.7' },
      },
    ];

    const geoJSON = ref.current.generateGeoJSON(markers);

    expect(geoJSON).toEqual({
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: {
            name: 'Vendor A',
            hours: '9-5',
            address: '123 Main St',
            'point-color': '253,237,57,1',
          },
          geometry: {
            type: 'Point',
            coordinates: [20, 10],
          },
        },
        {
          type: 'Feature',
          properties: {
            name: 'Vendor B',
            hours: '10-6',
            address: '456 Oak Ave',
            'point-color': '253,237,57,1',
          },
          geometry: {
            type: 'Point',
            coordinates: [40.7, 30.5],
          },
        },
      ],
    });
  });

  it('handles an empty markers array returning empty features', () => {
    const geoJSON = ref.current.generateGeoJSON([]);
    expect(geoJSON).toEqual({
      type: 'FeatureCollection',
      features: [],
    });
  });

  it('parses string coordinates to numbers', () => {
    const markers = [
      {
        name: 'Vendor C',
        hours: '',
        address: '',
        location: { latitude: '0.001', longitude: '0.002' },
      },
    ];

    const geoJSON = ref.current.generateGeoJSON(markers);
    const coords = geoJSON.features[0].geometry.coordinates;

    expect(typeof coords[0]).toBe('number');
    expect(typeof coords[1]).toBe('number');
    expect(coords).toEqual([0.002, 0.001]);
  });
});

describe('Sidebar.plotOnMap', () => {
  let mockMap;
  let ref;

  const createMockMap = () => {
    const map = {
      getLayer: jest.fn(),
      removeLayer: jest.fn(),
      getSource: jest.fn(),
      removeSource: jest.fn(),
      addSource: jest.fn(),
      addLayer: jest.fn(),
      // store calls for later inspection
      _addedSources: [],
      _addedLayers: [],
    };
    map.addSource.mockImplementation((name, cfg) => {
      map._addedSources.push({ name, cfg });
      return map;
    });
    map.addLayer.mockImplementation((cfg) => {
      map._addedLayers.push(cfg);
      return map;
    });
    return map;
  };

  const sampleResults = {
    trucks: [
      {
        name: 'Taco Bell',
        branches: [
          {
            location: { latitude: '10', longitude: '20' },
            schedule: '9-5',
            hours: '9-5',
            address: '123 Main St',
          },
        ],
      },
      {
        name: 'Burger King',
        branches: [
          {
            location: { latitude: '30', longitude: '40' },
            schedule: '10-6',
            hours: '10-6',
            address: '456 Oak Ave',
          },
        ],
      },
    ],
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockMap = createMockMap();
    ref = React.createRef();
    render(<Sidebar ref={ref} map={mockMap} />);
    // set the component state to have the sample results
    act(() => {
      ref.current.setState({ results: sampleResults, firstLoad: false });
    });
  });

  it('adds only the usual trucks source/layer when no vendor is provided', () => {
    act(() => {
      ref.current.plotOnMap();
    });

    // should attempt to remove existing layers/sources
    expect(mockMap.getLayer).toHaveBeenCalledWith('trucks');
    expect(mockMap.getSource).toHaveBeenCalledWith('trucks');
    expect(mockMap.getLayer).toHaveBeenCalledWith('trucks-highlight');
    expect(mockMap.getSource).toHaveBeenCalledWith('trucks-highlight');

    // only one source added (the usual trucks)
    expect(mockMap._addedSources).toHaveLength(1);
    const usualSource = mockMap._addedSources[0];
    expect(usualSource.name).toBe('trucks');
    expect(usualSource.cfg.type).toBe('geojson');
    // there are two branches → two features
    expect(usualSource.cfg.data.features).toHaveLength(2);

    // only one layer added (the usual trucks)
    expect(mockMap._addedLayers).toHaveLength(1);
    const usualLayer = mockMap._addedLayers[0];
    expect(usualLayer.id).toBe('trucks');
    expect(usualLayer.type).toBe('circle');

    // highlight source/layer should not be added
    expect(mockMap._addedSources.some(s => s.name === 'trucks-highlight')).toBeFalsy();
    expect(mockMap._addedLayers.some(l => l.id === 'trucks-highlight')).toBeFalsy();
  });

  it('adds separate highlight source/layer when a vendor is specified', () => {
    act(() => {
      ref.current.plotOnMap('taco bell');
    });

    // both usual and highlight sources should be added
    expect(mockMap._addedSources).toHaveLength(2);
    const usualSource = mockMap._addedSources.find(s => s.name === 'trucks');
    const highlightSource = mockMap._addedSources.find(s => s.name === 'trucks-highlight');

    expect(usualSource).toBeDefined();
    expect(highlightSource).toBeDefined();

    // usual source should contain the non‑matching truck (Burger King)
    expect(usualSource.cfg.data.features).toHaveLength(1);
    expect(usualSource.cfg.data.features[0].properties.name).toBe('Burger King');

    // highlight source should contain the matching truck (Taco Bell)
    expect(highlightSource.cfg.data.features).toHaveLength(1);
    expect(highlightSource.cfg.data.features[0].properties.name).toBe('Taco Bell');

    // both layers should be added
    expect(mockMap._addedLayers).toHaveLength(2);
    const usualLayer = mockMap._addedLayers.find(l => l.id === 'trucks');
    const highlightLayer = mockMap._addedLayers.find(l => l.id === 'trucks-highlight');

    expect(usualLayer).toBeDefined();
    expect(highlightLayer).toBeDefined();
    expect(highlightLayer.paint['circle-color']).toBe('rgba(164,65,99,1)');
  });
});

describe('Sidebar.handleSearch', () => {
  let mockEnd;
  let mockMap;

  beforeEach(() => {
    jest.clearAllMocks();

    // mock superagent request
    const request = require('superagent');
    mockEnd = jest.fn();
    request.get.mockReturnValue({ end: mockEnd });

    // simple mock map with chainable methods used in plotOnMap
    mockMap = {
      getLayer: jest.fn().mockReturnValue(false),
      removeLayer: jest.fn(),
      getSource: jest.fn().mockReturnValue(false),
      removeSource: jest.fn(),
      addSource: jest.fn().mockReturnThis(),
      addLayer: jest.fn().mockReturnThis(),
    };
  });

  it('submits query, fetches results and renders result summary', async () => {
    // prepare successful response body matching the shape used in Sidebar
    const responseBody = {
      hits: 1,
      locations: 2,
      trucks: [
        {
          name: 'Taco Truck',
          branches: [
            {
              location: { latitude: '0', longitude: '0' },
              schedule: [],
              hours: '9‑5',
              address: '123 Main St',
            },
          ],
        },
      ],
    };
    mockEnd.mockImplementationOnce((cb) => cb(null, { body: responseBody }));

    const ref = React.createRef();
    render(<Sidebar ref={ref} map={mockMap} />);

    // spy on plotOnMap to avoid heavy map interactions
    const plotSpy = jest.spyOn(ref.current, 'plotOnMap').mockImplementation(() => {});

    // type query
    fireEvent.change(screen.getByPlaceholderText(/Burgers, Tacos or Wraps\?/i), {
      target: { value: 'taco' },
    });

    // submit form (button inside the form)
    fireEvent.submit(screen.getByText(/Search!/i));

    // request should have been called with the correct query string
    const request = require('superagent');
    expect(request.get).toHaveBeenCalledWith('/search?q=taco');

    // wait for the heading that appears after successful fetch
    const heading = await screen.findByRole('heading', { level: 5 });
    expect(heading).toHaveTextContent(/Found/i);
    expect(plotSpy).toHaveBeenCalledTimes(1);
  });

  it('handles request error by showing an alert and does not render results', async () => {
    global.alert = jest.fn();
    mockEnd.mockImplementationOnce((cb) => cb(new Error('network error'), null));

    const ref = React.createRef();
    render(<Sidebar ref={ref} map={mockMap} />);

    const plotSpy = jest.spyOn(ref.current, 'plotOnMap').mockImplementation(() => {});

    fireEvent.change(screen.getByPlaceholderText(/Burgers, Tacos or Wraps\?/i), {
      target: { value: 'taco' },
    });
    fireEvent.submit(screen.getByText(/Search!/i));

    // wait for the async flow to finish
    await waitFor(() => {
      expect(global.alert).toHaveBeenCalledWith('error in fetching response');
    });

    // ensure no result heading is rendered
    expect(screen.queryByRole('heading', { level: 5 })).not.toBeInTheDocument();
    expect(plotSpy).not.toHaveBeenCalled();
  });
});

describe('Sidebar.onChange', () => {
  let mockMap;

  beforeEach(() => {
    mockMap = {
      getLayer: jest.fn(),
      removeLayer: jest.fn(),
      getSource: jest.fn(),
      removeSource: jest.fn(),
      addSource: jest.fn().mockReturnThis(),
      addLayer: jest.fn().mockReturnThis(),
    };
  });

  it('updates the input value when the user types', async () => {
    render(<Sidebar map={mockMap} />);
    const input = screen.getByPlaceholderText(
      /Burgers, Tacos or Wraps\?/i
    );
    fireEvent.change(input, { target: { value: 'tacos' } });
    expect(input).toHaveValue('tacos');
  });

  it('updates the input value when onChange is called programmatically', async () => {
    const ref = React.createRef();
    render(<Sidebar ref={ref} map={mockMap} />);
    const input = screen.getByPlaceholderText(
      /Burgers, Tacos or Wraps\?/i
    );

    act(() => {
      ref.current.onChange({ target: { value: 'burgers' } });
    });

    expect(input).toHaveValue('burgers');
  });
});

describe('Sidebar.handleHover', () => {
  let mockMap;
  let ref;

  beforeEach(() => {
    jest.clearAllMocks();

    mockMap = {
      getLayer: jest.fn().mockReturnValue(true),
      removeLayer: jest.fn(),
      getSource: jest.fn().mockReturnValue(true),
      removeSource: jest.fn(),
      addSource: jest.fn().mockReturnThis(),
      addLayer: jest.fn().mockReturnThis(),
    };

    ref = React.createRef();
  });

  const setResultsState = (instance) => {
    const mockResults = {
      trucks: [
        {
          name: 'VendorA',
          branches: [
            {
              location: { longitude: '10', latitude: '20' },
              schedule: [],
              hours: '9-5',
              address: '123 Main St',
            },
          ],
        },
        {
          name: 'VendorB',
          branches: [
            {
              location: { longitude: '30', latitude: '40' },
              schedule: [],
              hours: '10-6',
              address: '456 Side Rd',
            },
          ],
        },
      ],
    };
    act(() => {
      instance.setState({ results: mockResults, firstLoad: false, query: '' });
    });
  };

  it('delegates to plotOnMap with the supplied vendor name and adds highlight layers', () => {
    render(<Sidebar ref={ref} map={mockMap} />);
    setResultsState(ref.current);

    const plotSpy = jest.spyOn(ref.current, 'plotOnMap');

    act(() => {
      ref.current.handleHover('VendorA');
    });

    expect(plotSpy).toHaveBeenCalledWith('VendorA');

    // removal of any existing layers/sources
    expect(mockMap.removeLayer).toHaveBeenCalledTimes(2);
    expect(mockMap.removeSource).toHaveBeenCalledTimes(2);

    // addition of both regular and highlight sources/layers
    expect(mockMap.addSource).toHaveBeenCalledTimes(2);
    expect(mockMap.addSource).toHaveBeenCalledWith(
      'trucks',
      expect.objectContaining({ type: 'geojson' })
    );
    expect(mockMap.addSource).toHaveBeenCalledWith(
      'trucks-highlight',
      expect.objectContaining({ type: 'geojson' })
    );

    expect(mockMap.addLayer).toHaveBeenCalledTimes(2);
    expect(mockMap.addLayer).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'trucks' })
    );
    expect(mockMap.addLayer).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'trucks-highlight' })
    );
  });

  it('delegates to plotOnMap without a vendor name and adds only the regular trucks layer', () => {
    render(<Sidebar ref={ref} map={mockMap} />);
    setResultsState(ref.current);

    const plotSpy = jest.spyOn(ref.current, 'plotOnMap');

    act(() => {
      ref.current.handleHover(undefined);
    });

    expect(plotSpy).toHaveBeenCalledWith(undefined);

    // removal of any existing layers/sources (same as above)
    expect(mockMap.removeLayer).toHaveBeenCalledTimes(2);
    expect(mockMap.removeSource).toHaveBeenCalledTimes(2);

    // only the regular trucks source/layer should be added
    expect(mockMap.addSource).toHaveBeenCalledTimes(1);
    expect(mockMap.addSource).toHaveBeenCalledWith(
      'trucks',
      expect.objectContaining({ type: 'geojson' })
    );
    expect(mockMap.addSource).not.toHaveBeenCalledWith(
      'trucks-highlight',
      expect.anything()
    );

    expect(mockMap.addLayer).toHaveBeenCalledTimes(1);
    expect(mockMap.addLayer).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'trucks' })
    );
    expect(mockMap.addLayer).not.toHaveBeenCalledWith(
      expect.objectContaining({ id: 'trucks-highlight' })
    );
  });
});
