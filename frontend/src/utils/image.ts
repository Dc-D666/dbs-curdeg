/** 图片 URL 处理：QQ 频道 CDN 防盗链重写。
 *
 * channelgz.photo.store.qq.com 等域名校验 Referer，非 QQ 站点直接 <img> 引用会 403。
 * 渲染层统一把这类外链重写为后端代理（/api/v1/img_proxy?url=…），由服务端取回
 * （不发 Referer）。同时后端代理对非白名单域名拒绝，避免被滥用为开放代理。
 */
const PROXY_HOSTS = ['channelgz.photo.store.qq.com', 'channel.photo.store.qq.com']

/** 是否为会被防盗链拦截的 QQ CDN 外链。 */
export function isQqCdnImage(url: string): boolean {
  return PROXY_HOSTS.some((h) => url.startsWith(`https://${h}/`) || url.startsWith(`http://${h}/`))
}

/** 把 QQ CDN 外链重写为后端代理地址；其余 URL 原样返回。 */
export function proxifyImage(url: string): string {
  if (url && isQqCdnImage(url)) {
    return `/api/v1/img_proxy?url=${encodeURIComponent(url)}`
  }
  return url
}
