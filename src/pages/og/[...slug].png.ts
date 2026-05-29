/* eslint-disable style/no-multi-spaces */
/* eslint-disable node/prefer-global/process */
import type { APIRoute } from 'astro'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { Resvg } from '@resvg/resvg-js'
import { getCollection } from 'astro:content'
import satori from 'satori'

/* ── Font (process.cwd() resolves to project root during Astro builds) */
const fontRegular = readFileSync(join(process.cwd(), 'node_modules/@fontsource/inter/files/inter-latin-400-normal.woff'))
const fontBold = readFileSync(join(process.cwd(), 'node_modules/@fontsource/inter/files/inter-latin-700-normal.woff'))

/* ── OG card design ────────────────────────────────────────────────── */
function buildCard(title: string, subtitle: string, type: 'blog' | 'page') {
  return {
    type: 'div',
    props: {
      style: {
        width: '1200px',
        height: '630px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'flex-end',
        padding: '72px 80px',
        background: 'linear-gradient(135deg, #0d1b3e 0%, #1a2d5a 60%, #0d1b3e 100%)',
        position: 'relative',
        fontFamily: 'Inter',
      },
      children: [
        /* Gold accent bar */
        {
          type: 'div',
          props: {
            style: {
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '5px',
              background: 'linear-gradient(90deg, #D4A843, #e8734a)',
            },
          },
        },
        /* Church name top-left */
        {
          type: 'div',
          props: {
            style: {
              position: 'absolute',
              top: '48px',
              left: '80px',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
            },
            children: [
              {
                type: 'div',
                props: {
                  style: {
                    width: '36px',
                    height: '36px',
                    borderRadius: '50%',
                    background: '#D4A843',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  },
                  children: [{
                    type: 'div',
                    props: {
                      style: { width: '3px', height: '18px', background: '#0d1b3e', position: 'absolute' },
                    },
                  }, {
                    type: 'div',
                    props: {
                      style: { width: '18px', height: '3px', background: '#0d1b3e', position: 'absolute', marginTop: '-4px' },
                    },
                  }],
                },
              },
              {
                type: 'span',
                props: {
                  style: { color: 'rgba(255,255,255,0.7)', fontSize: '18px', letterSpacing: '2px', textTransform: 'uppercase' },
                  children: 'Jesus House Jamaica',
                },
              },
            ],
          },
        },
        /* Category pill */
        {
          type: 'div',
          props: {
            style: {
              display: 'flex',
              alignItems: 'center',
              marginBottom: '20px',
            },
            children: [{
              type: 'span',
              props: {
                style: {
                  color: '#D4A843',
                  fontSize: '14px',
                  fontWeight: 700,
                  letterSpacing: '3px',
                  textTransform: 'uppercase',
                },
                children: type === 'blog' ? subtitle : 'RCCG · Kingston, Jamaica',
              },
            }],
          },
        },
        /* Title */
        {
          type: 'div',
          props: {
            style: {
              color: '#ffffff',
              fontSize: title.length > 50 ? '48px' : '60px',
              fontWeight: 900,
              lineHeight: 1.1,
              maxWidth: '900px',
            },
            children: title,
          },
        },
        /* Bottom tagline */
        {
          type: 'div',
          props: {
            style: {
              position: 'absolute',
              bottom: '48px',
              right: '80px',
              color: 'rgba(255,255,255,0.4)',
              fontSize: '16px',
              letterSpacing: '1px',
            },
            children: 'Empowering men and women for godly living',
          },
        },
      ],
    },
  }
}

/* ── Static pages catalogue ────────────────────────────────────────── */
const STATIC_PAGES = [
  { slug: 'home',               title: 'Jesus House Jamaica',    subtitle: 'RCCG Kingston' },
  { slug: 'about',              title: 'About Us',               subtitle: 'Our Story' },
  { slug: 'sermons',            title: 'Sermons',                subtitle: 'The Word, Delivered' },
  { slug: 'blog',               title: 'Blog',                   subtitle: 'Devotionals & News' },
  { slug: 'contact',            title: 'Contact',                subtitle: 'Get in Touch' },
  { slug: 'events',             title: 'Events',                 subtitle: 'What\'s Happening' },
  { slug: 'our-mission',        title: 'Our Mission',            subtitle: 'Why We Exist' },
  { slug: 'our-values',         title: 'Our Values',             subtitle: 'What Drives Us' },
  { slug: 'our-beliefs',        title: 'Our Beliefs',            subtitle: 'What We Stand On' },
  { slug: 'our-pastors',        title: 'Our Pastors',            subtitle: 'Leadership' },
  { slug: 'our-confession',     title: 'Our Confession',         subtitle: 'Statement of Faith' },
  { slug: 'services',           title: 'Services',               subtitle: 'Join Us' },
  { slug: 'departments',        title: 'Departments',            subtitle: 'Ministries' },
  { slug: 'watch-live',         title: 'Watch Live',             subtitle: 'Stream with Us' },
  { slug: 'multimedia',         title: 'Multimedia',             subtitle: 'Watch & Listen' },
  { slug: 'general-overseers',  title: 'General Overseers',      subtitle: 'RCCG Leadership' },
  { slug: 'history-of-rccg',    title: 'History of RCCG',        subtitle: 'Our Heritage' },
  { slug: 'youth-conference',   title: 'Youth Conference',       subtitle: 'Next Generation' },
  { slug: 'board-of-trustees',  title: 'Board of Trustees',      subtitle: 'Governance' },
]

/* ── getStaticPaths ────────────────────────────────────────────────── */
export async function getStaticPaths() {
  const posts = await getCollection('blog')

  const blogPaths = posts.map(post => ({
    params: { slug: `blog/${post.id}` },
    props: { title: post.data.title, subtitle: post.data.category, type: 'blog' as const },
  }))

  const staticPaths = STATIC_PAGES.map(p => ({
    params: { slug: p.slug },
    props: { title: p.title, subtitle: p.subtitle, type: 'page' as const },
  }))

  return [...staticPaths, ...blogPaths]
}

/* ── Route handler ─────────────────────────────────────────────────── */
export const GET: APIRoute = async ({ props }) => {
  const { title, subtitle, type } = props as {
    title: string
    subtitle: string
    type: 'blog' | 'page'
  }

  const svg = await satori(buildCard(title, subtitle, type) as any, {
    width: 1200,
    height: 630,
    fonts: [
      { name: 'Inter', data: fontRegular, weight: 400, style: 'normal' },
      { name: 'Inter', data: fontBold,    weight: 700, style: 'normal' },
    ],
  })

  const resvg = new Resvg(svg, { fitTo: { mode: 'width', value: 1200 } })
  const png = resvg.render().asPng()

  return new Response(png as BodyInit, {
    headers: { 'Content-Type': 'image/png', 'Cache-Control': 'public, max-age=31536000, immutable' },
  })
}
