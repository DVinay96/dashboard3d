import { getIdentity, setIdentity } from './identity'

describe('identidad "ver como"', () => {
  it('se guarda en localStorage y en cookie (para <img> y descargas)', () => {
    setIdentity({ actAs: 'u1', clientId: 'c1' })
    expect(getIdentity()).toEqual({ actAs: 'u1', clientId: 'c1' })
    expect(document.cookie).toContain('x-act-as=u1')
    expect(document.cookie).toContain('x-client-id=c1')
    expect(JSON.parse(localStorage.getItem('pipeline3d.identity')!)).toEqual({ actAs: 'u1', clientId: 'c1' })
  })
  it('al limpiar se borran las cookies', () => {
    setIdentity({ actAs: null, clientId: null })
    expect(document.cookie).not.toContain('x-act-as')
    expect(document.cookie).not.toContain('x-client-id')
  })
})
