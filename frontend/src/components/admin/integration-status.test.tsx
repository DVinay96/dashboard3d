import { render, screen } from '@testing-library/react'
import { IntegrationStatus } from './integration-status'
import type { Integration } from '@/api/types'

const base = { id: 'i1', kind: 'meshy', name: 'Meshy', enabled: true, config: {}, secrets: {}, last_status: null, last_message: null, last_at: null } as Integration

describe('IntegrationStatus', () => {
  it('distingue sin conectar, sin probar, ok y fallo', () => {
    const { rerender } = render(<IntegrationStatus integration={base} configured={false} />)
    expect(screen.getByText('Sin conectar.')).toBeInTheDocument()
    rerender(<IntegrationStatus integration={base} configured />)
    expect(screen.getByText(/sin probar todavía/)).toBeInTheDocument()
    rerender(<IntegrationStatus integration={{ ...base, last_status: 'OK', last_message: 'Conectado.', last_at: 1 }} configured />)
    expect(screen.getByText(/Conectado\./)).toBeInTheDocument()
    rerender(<IntegrationStatus integration={{ ...base, last_status: 'FAILED', last_message: 'HTTP 401', last_at: 1 }} configured />)
    expect(screen.getByRole('alert')).toHaveTextContent('HTTP 401')
  })
})
