import { defaultPolycount, estimateCredits, exceedsBudget, expectedTris, isModelFile, isPhotoFile } from './generation'

const base = { isLocalModel: false, textureResolution: '2k', ultra: false, model: 'meshy-6', remesh: false }

describe('estimateCredits', () => {
  it('un modelo local no gasta creditos', () => {
    expect(estimateCredits({ ...base, isLocalModel: true, ultra: true, remesh: true })).toBe(0)
  })
  it('suma por resolucion, ultra y remesh', () => {
    expect(estimateCredits(base)).toBe(30)
    expect(estimateCredits({ ...base, textureResolution: '8k' })).toBe(35)
    expect(estimateCredits({ ...base, remesh: true })).toBe(35)
    expect(estimateCredits({ ...base, ultra: true, model: 'meshy-7' })).toBe(35)
    expect(estimateCredits({ ...base, ultra: true, model: 'latest', remesh: true, textureResolution: '8k' })).toBe(45)
  })
  it('ultra solo cuenta en v7 y latest', () => {
    expect(estimateCredits({ ...base, ultra: true, model: 'meshy-6' })).toBe(30)
  })
})

describe('polycount', () => {
  it('con quads se pide la mitad del budget (1 quad = 2 tris)', () => {
    expect(defaultPolycount(15000, 'quad')).toBe(7500)
    expect(defaultPolycount(15000, 'triangle')).toBe(15000)
    expect(defaultPolycount(50, 'quad')).toBe(100)
  })
  it('avisa cuando lo pedido supera el budget en mas de 5%', () => {
    expect(expectedTris(7500, 'quad')).toBe(15000)
    expect(exceedsBudget(7500, 'quad', 15000)).toBe(false)
    expect(exceedsBudget(7900, 'quad', 15000)).toBe(true)
    expect(exceedsBudget(15700, 'triangle', 15000)).toBe(false)
    expect(exceedsBudget(15800, 'triangle', 15000)).toBe(true)
  })
})

describe('tipos de archivo', () => {
  it('distingue fotos y modelos', () => {
    expect(isModelFile('Silla.GLB')).toBe(true)
    expect(isModelFile('a.gltf')).toBe(true)
    expect(isModelFile('a.png')).toBe(false)
    expect(isPhotoFile('a.JPEG')).toBe(true)
    expect(isPhotoFile('a.glb')).toBe(false)
  })
})
