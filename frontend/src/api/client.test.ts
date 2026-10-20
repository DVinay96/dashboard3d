import { detailMessage } from './client'

describe('detailMessage', () => {
  it('texto tal cual', () => {
    expect(detailMessage('No existe')).toBe('No existe')
  })
  it('errores de validacion de FastAPI', () => {
    expect(detailMessage([{ loc: ['body', 'name'], msg: 'Field required' }, { loc: ['body'], msg: 'otro' }])).toBe('name: Field required · otro')
  })
  it('usa el texto de respaldo si no entiende el formato', () => {
    expect(detailMessage(undefined, 'Falló')).toBe('Falló')
    expect(detailMessage({}, 'Falló')).toBe('Falló')
  })
})
