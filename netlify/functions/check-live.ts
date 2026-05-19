import type { Context } from '@netlify/functions'

const CHANNEL_ID = 'UCO1S3nxtFg0_HXEMuZji5zg'
const LIVE_URL = `https://www.youtube.com/@jesushousekingston/live`
const RSS_URL = `https://www.youtube.com/feeds/videos.xml?channel_id=${CHANNEL_ID}`
const YT_SEARCH_API = 'https://www.googleapis.com/youtube/v3/search'

const SCRAPE_HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
  'Accept-Language': 'en-US,en;q=0.9',
}

// ── YouTube Data API v3 (preferred when YOUTUBE_API_KEY is set) ──────────────
// Costs 100 quota units per call (daily free limit: 10,000 units).
async function checkViaApi(apiKey: string): Promise<{ isLive: boolean, videoId: string | null }> {
  const url = new URL(YT_SEARCH_API)
  url.searchParams.set('part', 'id')
  url.searchParams.set('channelId', CHANNEL_ID)
  url.searchParams.set('eventType', 'live')
  url.searchParams.set('type', 'video')
  url.searchParams.set('maxResults', '1')
  url.searchParams.set('key', apiKey)

  const res = await fetch(url)
  if (!res.ok)
    throw new Error(`YouTube API ${res.status}`)

  const data = await res.json() as { items?: Array<{ id: { videoId: string } }> }
  const videoId = data.items?.[0]?.id?.videoId ?? null
  return { isLive: videoId !== null, videoId }
}

// ── Scraping fallback (no API key) ───────────────────────────────────────────
async function checkViaScrape(): Promise<{ isLive: boolean, videoId: string | null }> {
  const [liveRes, rssRes] = await Promise.all([
    fetch(LIVE_URL, { headers: SCRAPE_HEADERS }),
    fetch(RSS_URL),
  ])

  const [html, xml] = await Promise.all([liveRes.text(), rssRes.text()])

  const isLive = html.includes('"isLive":true') || html.includes('"isLiveNow":true')
  const rssMatch = xml.match(/<yt:videoId>([\w-]{11})<\/yt:videoId>/)
  const videoId = rssMatch ? rssMatch[1] : null

  return { isLive, videoId: isLive ? videoId : null }
}

export default async (_req: Request, _ctx: Context) => {
  try {
    // eslint-disable-next-line node/prefer-global/process
    const apiKey = process.env.YOUTUBE_API_KEY
    const result = apiKey
      ? await checkViaApi(apiKey)
      : await checkViaScrape()

    return Response.json(result, { headers: { 'Cache-Control': 'no-store, max-age=0' } })
  }
  catch {
    return Response.json({ isLive: false, videoId: null }, { status: 200 })
  }
}

export const config = { path: '/api/check-live' }
