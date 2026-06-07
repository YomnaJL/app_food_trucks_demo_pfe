// Functions inlined from source (not require'd — avoids browser globals)

function formatHTMLforMarker(props) {
  var { name, hours, address } = props;
  var html =
    '<div class="marker-title">' +
    name +
    "</div>" +
    "<h4>Operating Hours</h4>" +
    "<span>" +
    hours +
    "</span>" +
    "<h4>Address</h4>" +
    "<span>" +
    address +
    "</span>";
  return html;
}

describe('formatHTMLforMarker', () => {
  it('should return correctly formatted HTML for typical props', () => {
    const props = {
      name: 'Food Truck',
      hours: '9am - 5pm',
      address: '123 Main St',
    };
    const expected =
      '<div class="marker-title">Food Truck</div>' +
      '<h4>Operating Hours</h4>' +
      '<span>9am - 5pm</span>' +
      '<h4>Address</h4>' +
      '<span>123 Main St</span>';
    const result = formatHTMLforMarker(props);
    expect(result).toBe(expected);
  });

  it('should handle empty strings in props', () => {
    const props = {
      name: '',
      hours: '',
      address: '',
    };
    const expected =
      '<div class="marker-title"></div>' +
      '<h4>Operating Hours</h4>' +
      '<span></span>' +
      '<h4>Address</h4>' +
      '<span></span>';
    const result = formatHTMLforMarker(props);
    expect(result).toBe(expected);
  });

  it('should convert non‑string values to strings', () => {
    const props = {
      name: 42,
      hours: false,
      address: null,
    };
    const expected =
      '<div class="marker-title">42</div>' +
      '<h4>Operating Hours</h4>' +
      '<span>false</span>' +
      '<h4>Address</h4>' +
      '<span>null</span>';
    const result = formatHTMLforMarker(props);
    expect(result).toBe(expected);
  });

  it('should output "undefined" for missing properties', () => {
    const props = {};
    const expected =
      '<div class="marker-title">undefined</div>' +
      '<h4>Operating Hours</h4>' +
      '<span>undefined</span>' +
      '<h4>Address</h4>' +
      '<span>undefined</span>';
    const result = formatHTMLforMarker(props);
    expect(result).toBe(expected);
  });

  it('should throw a TypeError when called with null', () => {
    expect(() => formatHTMLforMarker(null)).toThrow(TypeError);
  });

  it('should throw a TypeError when called with undefined', () => {
    expect(() => formatHTMLforMarker(undefined)).toThrow(TypeError);
  });
});
