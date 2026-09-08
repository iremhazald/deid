export type ProjectLinkKey = 'github' | 'documentation' | 'privacy' | 'license'

export type ProjectLink = {
  key: ProjectLinkKey
  url: string
  primary?: boolean
}

function configuredUrl(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined
  return value.trim() || undefined
}

const urls: Record<ProjectLinkKey, string | undefined> = {
  github: configuredUrl(import.meta.env.VITE_GITHUB_URL),
  documentation: configuredUrl(import.meta.env.VITE_DOCUMENTATION_URL),
  privacy: configuredUrl(import.meta.env.VITE_PRIVACY_URL),
  license: configuredUrl(import.meta.env.VITE_LICENSE_URL),
}

export function githubUrl(): string | undefined {
  return urls.github
}

/**
 * Only configured destinations are rendered. This deliberately avoids fake or
 * guessed project, documentation, privacy, and license URLs.
 */
export function projectLinks(): ProjectLink[] {
  return (Object.entries(urls) as Array<[ProjectLinkKey, string | undefined]>)
    .filter((entry): entry is [ProjectLinkKey, string] => Boolean(entry[1]))
    .map(([key, url]) => ({
      key,
      url,
      primary: key === 'github',
    }))
}
