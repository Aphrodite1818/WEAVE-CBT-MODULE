import { existsSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const srcRoot = fileURLToPath(new URL('../src/', import.meta.url))

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
    const unexpected = readdirSync(srcRoot).filter((entry) => !allowedTopLevelEntries.has(entry))
    expect(unexpected).toEqual([])
  })
})
