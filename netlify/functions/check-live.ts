import type { Context } from '@netlify/functions'

const LIVE_URL = 'https://www.youtube.com/@jesushousekingston/live'

export default async (_req: Request, _ctx: Context) => {
  try {
    const res = await fetch(LIVE_URL, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
      },
    })

    const html = await res.text()

    const isLive = html.includes('"isLive":true') || html.includes('"isLiveNow":true')

    // ytInitialPlayerResponse.videoDetails is the authoritative source for the live video ID
    let videoId: string | null = null
    const playerResponse = html.match(/ytInitialPlayerResponse\s*=\s*(\{.+?\});\s*(?:var |<\/script)/)
    if (playerResponse) {
      try {
        const data = JSON.parse(playerResponse[1]) as { videoDetails?: { videoId?: string } }
        videoId = data.videoDetails?.videoId ?? null
      }
      catch { /* malformed JSON — fall through */ }
    }

    return Response.json(
      { isLive, videoId },
      { headers: { 'Cache-Control': 'no-store, max-age=0' } },
    )
  }
  catch {
    return Response.json({ isLive: false, videoId: null }, { status: 200 })
  }
}

export const config = { path: '/api/check-live' }
