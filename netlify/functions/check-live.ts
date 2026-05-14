import type { Context } from '@netlify/functions'

const CHANNEL_ID = 'UCO1S3nxtFg0_HXEMuZji5zg'
const LIVE_URL = `https://www.youtube.com/@jesushousekingston/live`
const RSS_URL = `https://www.youtube.com/feeds/videos.xml?channel_id=${CHANNEL_ID}`

const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
  'Accept-Language': 'en-US,en;q=0.9',
}

export default async (_req: Request, _ctx: Context) => {
  try {
    // Fetch both in parallel — RSS for video ID, live page for isLive confirmation
    const [liveRes, rssRes] = await Promise.all([
      fetch(LIVE_URL, { headers: HEADERS }),
      fetch(RSS_URL),
    ])

    const [html, xml] = await Promise.all([liveRes.text(), rssRes.text()])

    const isLive = html.includes('"isLive":true') || html.includes('"isLiveNow":true')

    // RSS always returns the channel's most recent video ID reliably
    const rssMatch = xml.match(/<yt:videoId>([a-zA-Z0-9_-]{11})<\/yt:videoId>/)
    const videoId = rssMatch ? rssMatch[1] : null

    return Response.json(
      { isLive, videoId: isLive ? videoId : null },
      { headers: { 'Cache-Control': 'no-store, max-age=0' } },
    )
  }
  catch {
    return Response.json({ isLive: false, videoId: null }, { status: 200 })
  }
}

export const config = { path: '/api/check-live' }
