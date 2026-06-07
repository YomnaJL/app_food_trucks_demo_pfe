import React from 'react';
    import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import Intro from '../../../../flask_app/static/src/components/Intro';

describe('Intro', () => {
  it('renders the About heading', () => {
    render(<Intro />);
    expect(
      screen.getByRole('heading', { level: 3, name: /about/i })
    ).toBeInTheDocument();
  });

  it('renders the static informational paragraphs', () => {
    render(<Intro />);

    // First paragraph – partial text before the link
    expect(
      screen.getByText(/fun application built to accompany the/i)
    ).toBeInTheDocument();

    // Link inside the first paragraph
    expect(
      screen.getByRole('link', { name: /docker curriculum/i })
    ).toBeInTheDocument();

    // Second paragraph
    expect(screen.getByText(/Flask on the backend/i)).toBeInTheDocument();

    // Third paragraph
    expect(
      screen.getByText(/hand-crafted with React/i)
    ).toBeInTheDocument();

    // Fourth paragraph – the Genius link
    expect(
      screen.getByRole('link', { name: /genius/i })
    ).toBeInTheDocument();

    // Fifth paragraph – the SF Data link
    expect(
      screen.getByRole('link', { name: /sf data/i })
    ).toBeInTheDocument();
  });
});
