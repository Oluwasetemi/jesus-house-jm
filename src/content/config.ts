import { defineCollection, z } from 'astro:content'

const blog = defineCollection({
  type: 'content',
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

export const collections = { blog }
