import type {NextConfig} from 'next';
const config: NextConfig={output:process.env.VERCEL?undefined:'standalone',experimental:{proxyClientMaxBodySize:'110mb'},async headers(){return [{source:'/:path*',headers:[{key:'X-Content-Type-Options',value:'nosniff'},{key:'Referrer-Policy',value:'no-referrer'},{key:'X-Frame-Options',value:'DENY'}]}];}};
export default config;
