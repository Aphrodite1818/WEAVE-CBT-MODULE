import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import App from '../src/App'

describe('App', () => {
  it('renders the starter page and updates the counter', () => {
    render(<App />)

    expect(
      screen.getByRole('heading', { name: /get started/i }),
    ).toBeInTheDocument()

    const counter = screen.getByRole('button', { name: /count is 0/i })
    fireEvent.click(counter)

    expect(
      screen.getByRole('button', { name: /count is 1/i }),
    ).toBeInTheDocument()
  })
})
