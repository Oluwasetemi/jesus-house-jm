import { glob } from 'astro/loaders'
import { defineCollection, z } from 'astro:content'

const blog = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/blog' }),
  schema: z.object({
    title: z.string(),
    excerpt: z.string(),
    category: z.enum(['devotionals', 'news', 'faith', 'community']),
    date: z.string(),
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
    date: z.string(),
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
    date: z.string(),
    description: z.string().optional(),
    coverImage: z.string().optional(),
    images: z.array(z.object({
      url: z.string(),
      alt: z.string(),
      caption: z.string().optional(),
    })),
  }),
})

export const collections = { blog, events, gallery }
