import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FieldsEditor } from './fields-editor'
import type { FieldDef } from '@/api/types'

const select: FieldDef = { key: 'color', label: 'Color', type: 'select', required: true, options: ['rojo', 'azul'], default: '', help: '' }

describe('FieldsEditor', () => {
  it('muestra los campos iniciales y su clave', () => {
    render(<FieldsEditor initial={[select]} onChange={() => {}} />)
    expect(screen.getByDisplayValue('Color')).toBeInTheDocument()
    expect(screen.getByDisplayValue('rojo, azul')).toBeInTheDocument()
    expect(screen.getByText('clave: color')).toBeInTheDocument()
  })

  it('no pierde la coma mientras se escriben las opciones', async () => {
    const onChange = vi.fn()
    render(<FieldsEditor initial={[select]} onChange={onChange} />)
    const input = screen.getByLabelText('Opciones')
    await userEvent.clear(input)
    await userEvent.type(input, 'a, b,')
    expect(input).toHaveValue('a, b,')
    expect(onChange).toHaveBeenLastCalledWith([expect.objectContaining({ options: ['a', 'b'] })])
  })

  it('agrega y quita campos', async () => {
    const onChange = vi.fn()
    render(<FieldsEditor initial={[]} onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: /campo/i }))
    await userEvent.type(screen.getByLabelText('Nombre visible'), 'Peso')
    expect(onChange).toHaveBeenLastCalledWith([expect.objectContaining({ label: 'Peso', type: 'text', options: [] })])
    await userEvent.click(screen.getByRole('button', { name: 'Quitar Peso' }))
    expect(onChange).toHaveBeenLastCalledWith([])
  })

  it('las opciones solo viajan en los campos tipo lista', async () => {
    const onChange = vi.fn()
    render(<FieldsEditor initial={[select]} onChange={onChange} />)
    await userEvent.selectOptions(screen.getByLabelText('Tipo'), 'text')
    expect(onChange).toHaveBeenLastCalledWith([expect.objectContaining({ type: 'text', options: [] })])
  })
})
