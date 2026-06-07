import React from 'react';
    import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import Vendor from '../../../../flask_app/static/src/components/Vendor';

describe('Vendor.formatFoodItems', () => {
  const createProps = (overrides = {}) => ({
    data: {
      name: 'Test Vendor',
      branches: [{}],
      fooditems: [],
      drinks: false,
      ...overrides,
    },
    handleHover: jest.fn(),
  });

  it('returns the full joined string when not expanded and the list is short', () => {
    const props = createProps();
    const ref = React.createRef();
    render(<Vendor ref={ref} {...props} />);
    const items = ['Apple', 'Banana'];
    const result = ref.current.formatFoodItems(items);
    expect(result).toBe('Apple, Banana');
  });

  it('truncates a long list when not expanded', () => {
    const props = createProps();
    const ref = React.createRef();
    render(<Vendor ref={ref} {...props} />);
    const longItem = 'a'.repeat(100);
    const items = [longItem];
    const full = items.join(', ');
    const expected = full.substr(0, 80) + ' & more...';
    const result = ref.current.formatFoodItems(items);
    expect(result).toBe(expected);
  });

  it('returns the full joined string when expanded', () => {
    const foodItems = ['Apple', 'Banana', 'Cherry', 'Date'];
    const props = createProps({ fooditems: foodItems });
    const ref = React.createRef();
    render(<Vendor ref={ref} {...props} />);
    const li = screen.getByText(props.data.name).closest('li');
    fireEvent.click(li); // toggles isExpanded to true
    const result = ref.current.formatFoodItems(foodItems);
    expect(result).toBe(foodItems.join(', '));
  });
});

describe('Vendor.toggleExpand', () => {
  let defaultProps;

  beforeEach(() => {
    defaultProps = {
      data: {
        name: 'VendorX',
        branches: [{}, {}],
        fooditems: ['Apple', 'Banana', 'Cherry', 'Date', 'Elderberry', 'Fig', 'Grape', 'Honeydew'],
        drinks: true,
      },
      handleHover: jest.fn(),
    };
  });

  it('calls handleHover with the vendor name on mouse enter', () => {
    render(<Vendor {...defaultProps} />);
    const li = screen.getByRole('listitem');
    fireEvent.mouseEnter(li);
    expect(defaultProps.handleHover).toHaveBeenCalledTimes(1);
    expect(defaultProps.handleHover).toHaveBeenCalledWith('VendorX', expect.anything());
  });

  it('toggles expanded state and updates displayed food items', () => {
    // Ensure the list is long enough to trigger truncation when collapsed
    const longItems = Array(20).fill('Item');
    defaultProps.data.fooditems = longItems;

    render(<Vendor {...defaultProps} />);
    const li = screen.getByRole('listitem');

    // Verify collapsed rendering contains the truncation marker
    const collapsed = screen.getByText(/Serves .*& more\.\.\./i);
    expect(collapsed).toBeInTheDocument();

    // Click to expand
    fireEvent.click(li);

    // Verify full list is now rendered
    const fullText = `Serves ${longItems.join(', ')}`;
    const expanded = screen.getByText(fullText);
    expect(expanded).toBeInTheDocument();
  });
});
