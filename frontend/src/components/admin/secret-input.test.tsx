import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SecretInput } from './secret-input'

describe('SecretInput', () => {
  it('una clave guardada solo se indica, nunca se muestra', () => {
    render(<SecretInput label="API key" state={{ set: true, hint: '…1234' }} value="" onChange={() => {}} />)
    const input = screen.getByLabelText('API key')
    expect(input).toHaveValue('')
    expect(input).toHaveAttribute('type', 'password')
    expect(screen.getByText(/Guardada \(…1234\)/)).toBeInTheDocument()
  })

  it('sin clave guardada no promete nada', () => {
    render(<SecretInput label="API key" state={{ set: false, hint: '' }} value="" onChange={() => {}} />)
    expect(screen.queryByText(/Guardada/)).not.toBeInTheDocument()
  })

  it('avisa cada cambio', async () => {
    const onChange = vi.fn()
    render(<SecretInput label="Token" value="" onChange={onChange} />)
    await userEvent.type(screen.getByLabelText('Token'), 'ab')
    expect(onChange).toHaveBeenLastCalledWith('b')
  })
})
