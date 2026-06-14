import { glob } from 'astro/loaders'
import { z } from 'astro/zod'
import { defineCollection } from 'astro:content'

/* Decap CMS datetime widget writes unquoted YAML dates (e.g. 2026-07-04)
   which YAML parsers coerce to Date objects. This transform accepts both
   and normalises to YYYY-MM-DD string for consistent use in templates. */
const dateField = z.union([
  z.string(),
  z.date().transform(d => d.toISOString().split('T')[0]),
])

const blog = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/blog' }),
  schema: z.object({
    title: z.string(),
    excerpt: z.string(),
    category: z.enum(['devotionals', 'news', 'faith', 'community']),
    date: dateField,
    author: z.string(),
    readTime: z.string(),
    featured: z.boolean().default(false),
    coverImage: z.string().optional(),
  }),
})

const events = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/events' }),
  schema: z.object({
    title: z.string(),
    date: dateField,
    time: z.string(),
    location: z.string(),
    description: z.string(),
    image: z.string().optional(),
    featured: z.boolean().default(false),
    registrationUrl: z.string().optional(),
  }),
})

const gallery = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/gallery' }),
  schema: z.object({
    title: z.string(),
    date: dateField,
    description: z.string().optional(),
    coverImage: z.string().optional(),
    images: z.array(z.object({
      url: z.string(),
      alt: z.string(),
      caption: z.string().optional(),
    })),
  }),
})

const sermons = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/sermons' }),
  schema: z.object({
    videoId: z.string(),
    timestamp: z.number().optional(),
  }),
})

const podcast = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/podcast' }),
  schema: z.object({
    videoId: z.string(),
    episodeNumber: z.number().optional(),
    topics: z.array(z.string()).default([]),
  }),
})

export const collections = { blog, events, gallery, sermons, podcast }
