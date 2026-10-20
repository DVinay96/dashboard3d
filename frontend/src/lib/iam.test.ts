import { emptyStatement, parseLines, projectResources, statementProblems } from './iam'

describe('parseLines', () => {
  it('separa por linea o coma, recorta y deduplica', () => {
    expect(parseLines('a\n b ,c\n\na')).toEqual(['a', 'b', 'c'])
    expect(parseLines('  ')).toEqual([])
  })
})

describe('recursos', () => {
  it('un proyecto se acota con su id y con sus productos', () => {
    expect(projectResources('p1')).toEqual(['project/p1', 'project/p1/*'])
  })
})

describe('statementProblems', () => {
  it('detecta lo evidente', () => {
    expect(statementProblems([])).toMatch(/al menos un statement/)
    expect(statementProblems([emptyStatement()])).toMatch(/no tiene acciones/)
    expect(statementProblems([{ effect: 'allow', actions: ['a'], resources: [] }])).toMatch(/no tiene recursos/)
    expect(statementProblems([{ effect: 'deny', actions: ['a'], resources: ['*'] }])).toBeNull()
  })
})
