'use client';
import {useEffect,useRef,useState} from 'react';

// Resolve private images before mounting the isolated preview. Some browsers keep
// the first srcdoc document when it is changed during the initial frame load.
export default function Preview({html,title='상세페이지 미리보기'}:{html:string,title?:string}){
 const [ready,setReady]=useState<{source:string,document:string}|null>(null);
 const [failed,setFailed]=useState(false),[retry,setRetry]=useState(0);
 const cache=useRef(new Map<string,Promise<string>>());
 useEffect(()=>{
  let live=true;setFailed(false);
  const urls=Array.from(new Set(html.match(/\/api\/media\/[a-f0-9-]+/g)||[]));
  async function photo(url:string){
   if(!cache.current.has(url)){
    const pending=fetch(url,{credentials:'same-origin'}).then(async response=>{
     if(!response.ok)throw new Error('사진을 불러오지 못했습니다.');
     const blob=await response.blob();
     return new Promise<string>((resolve,reject)=>{
      const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=reject;reader.readAsDataURL(blob);
     });
    }).catch(error=>{cache.current.delete(url);throw error});
    cache.current.set(url,pending);
   }
   return [url,await cache.current.get(url)!] as const;
  }
  Promise.all(urls.map(photo)).then(pairs=>{
   let document=html;for(const [url,data] of pairs)document=document.replaceAll(url,()=>data);
   if(live)setReady({source:html,document});
  }).catch(()=>{if(live)setFailed(true)});
  return()=>{live=false};
 },[html,retry]);
 if(failed)return <div className="preview-message" role="alert"><p>미리보기 사진을 불러오지 못했습니다.</p><button className="secondary" onClick={()=>{setReady(null);setRetry(n=>n+1)}}>사진 다시 불러오기</button></div>;
 if(!ready||ready.source!==html)return <div className="preview-message" role="status">미리보기 사진을 준비하고 있습니다.</div>;
 return <iframe key={ready.document} className="preview-frame" title={title} sandbox="" referrerPolicy="no-referrer" srcDoc={`<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src https: data:; style-src 'unsafe-inline';"><style>body{margin:24px;font-family:Arial,sans-serif;font-size:16px;line-height:1.8;color:#272b30}img{max-width:100%;height:auto}h3{font-size:14px;letter-spacing:2px;margin-top:44px}table{max-width:100%}</style></head><body>${ready.document}</body></html>`}/>;
}
