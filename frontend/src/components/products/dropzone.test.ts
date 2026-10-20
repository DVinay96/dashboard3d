import { mergeFiles } from './dropzone'

const f = (name: string) => new File(['x'], name)

describe('mergeFiles', () => {
  it('acumula fotos hasta 4 e ignora lo que no sirve', () => {
    let files: File[] = []
    files = mergeFiles(files, [f('a.jpg'), f('b.png'), f('notas.txt')])
    expect(files.map((x) => x.name)).toEqual(['a.jpg', 'b.png'])
    files = mergeFiles(files, [f('c.jpg'), f('d.jpg'), f('e.jpg')])
    expect(files.map((x) => x.name)).toEqual(['a.jpg', 'b.png', 'c.jpg', 'd.jpg'])
  })
  it('un modelo reemplaza todo', () => {
    expect(mergeFiles([f('a.jpg')], [f('m.glb'), f('b.jpg')]).map((x) => x.name)).toEqual(['m.glb'])
  })
  it('las fotos nuevas reemplazan a un modelo previo', () => {
    expect(mergeFiles([f('m.glb')], [f('a.jpg')]).map((x) => x.name)).toEqual(['a.jpg'])
  })
})
