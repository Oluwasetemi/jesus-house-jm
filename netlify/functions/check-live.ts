import type { Context } from '@netlify/functions'

const CHANNEL_ID = 'UCO1S3nxtFg0_HXEMuZji5zg'

export default async (_req: Request, _ctx: Context) => {
  try {
    const res = await fetch(
      `https://www.youtube.com/channel/${CHANNEL_ID}/live`,
      {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
          'Accept-Language': 'en-US,en;q=0.9',
        },
      },
    )

    const html = await res.text()

    const isLive
      = html.includes('"isLive":true')
      || html.includes('"isLiveNow":true')

    // Extract the live video ID from the canonical <link> tag — this points
    // to the actual live video, not a related/recommended video
    let videoId: string | null = null
    const canonical = html.match(/<link rel="canonical" href="https:\/\/www\.youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})"/)
    if (canonical)
      videoId = canonical[1]

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
