import handler from '../netlify/functions/check-live.ts'

const res = await handler(new Request('http://localhost/api/check-live'), {} as never)
const data = await res.json()

console.log('Status:', res.status)
console.log('Result:', JSON.stringify(data, null, 2))
