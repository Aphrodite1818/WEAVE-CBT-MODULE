import { existsSync, readdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const srcRoot = resolve(process.cwd(), 'src')

const forbiddenLegacyDirectories = ['components', 'lib', 'services', 'state']
const allowedTopLevelEntries = new Set([
  'ARCHITECTURE.md',
  'App.jsx',
  'api',
  'app',
  'assets',
  'features',
  'main.jsx',
  'shared',
  'styles',
])

describe('frontend architecture', () => {
  it('does not recreate legacy generic source buckets', () => {
    for (const directory of forbiddenLegacyDirectories) {
      expect(existsSync(`${srcRoot}/${directory}`), directory).toBe(false)
    }
  })

  it('keeps source ownership inside the documented top-level boundaries', () => {
    const unexpected = readdirSync(srcRoot).filter((entry) => !allowedTopLevelEntries.has(entry) && readdirSync(resolve(srcRoot, entry)).length > 0)
    expect(unexpected).toEqual([])
  })
})
