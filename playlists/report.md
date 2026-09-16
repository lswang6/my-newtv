# Channel list build report

Reachability was measured from the TV (LAN) with its static curl and DNS over HTTPS. The TV reaches the internet through the router's proxy, whose egress is the same as the Mac's: an Oracle Cloud node in South Korea. Results therefore describe what that proxy can reach, not what a Chinese residential line would see.

## 央视
173 candidate urls, 20 channels passing.
Found in the playlists but not reachable: CCTV4 美洲, CGTN 纪录.

## 凤凰
16 candidate urls, 3 channels passing.

## 港台新闻
37 candidate urls, 5 channels passing.
Found in the playlists but not reachable: HOY 資訊台, HOY TV, RTHK 32, TVBS新聞, 東森財經新聞, 東森新聞, 民視新聞, 三立新聞, 華視新聞, 公視, 中視新聞, 台視新聞.
Not present in any source playlist: Now 新聞台, 有線新聞台, 中天新聞, 年代新聞, 非凡新聞, 寰宇新聞.

## 国际新闻
74 candidate urls, 17 channels passing.
Found in the playlists but not reachable: CNN International, CNN, ABC News Live.
Not present in any source playlist: BBC World News.

## 体育
195 candidate urls, 30 channels passing.
142 channels were matched and tested and 68 of them had a playable url; the list keeps the best 30, the preferred names first and the remainder by segment latency.
Matched but nothing playable from here: BBC Radio 5 Sports Extra, Bellator MMA, Billiard TV, CBS Sports Golazo Network, CBS Sports HQ, DAZN Combat, DAZN Darts x Pluto TV, DSports, DSports 2, ESPN 3, ETVN, FIFA+, Fight Network, Fox Sports 2, Golazo Network, Hard Knocks, Kabaddi 24x7, Lacrosse TV, MLB, MMA-TV, MUTV, Midpen Media Center Youth Education and Sports Channel 28, Monster Jam, NFL Channel, NFL Network, NHRA TV, NewTV精品体育, NewTV超级体育, Overtime, PBR RidePass, PFL MMA, Pluto TV Competition, Pluto TV E-Sports, Pluto TV Esportes, Pluto TV Snooker 900, Premier Sports, Premier Sports 1, Premier Sports 2, Racing.com, Rev'n Action, and 34 more.

## 卫视
304 candidate urls, 30 channels passing.
38 channels were matched and tested and 35 of them had a playable url; the list keeps the best 30, the preferred names first and the remainder by segment latency.
Matched but nothing playable from here: 兵团卫视, 康巴卫视, 海南卫视.

## 纪录片
51 candidate urls, 14 channels passing.
32 channels were matched and tested and 14 of them had a playable url; the list keeps the best 14, the preferred names first and the remainder by segment latency.
Matched but nothing playable from here: Curiosity Now, Docurama, History, History TV18, National Geographic, NewTV精品纪录, Sony BBC Earth, 上海纪实, 上海纪实人文, 北京纪实科教, 求索动物, 求索生活, 求索科学, 求索纪录, 精品纪录, 纪实人文, 纪实科教, 金鹰纪实.

## 港台综艺
23 candidate urls, 3 channels passing.
14 channels were matched and tested and 3 of them had a playable url; the list keeps the best 3, the preferred names first and the remainder by segment latency.
Matched but nothing playable from here: J2, 三立台灣台, 中天綜合台, 明珠台, 東森綜合台, 東森電影台, 民視台灣台, 民視第一台, 澳視澳門, 緯來電影台, 華視.

## Notes
Every China Mobile / cmvideo CCTV feed carried by the built-in lists times out or answers 403 from this egress; the CCTV streams that do work come from overseas mirrors, which hand out redirect URLs signed against the client IP, so the unsigned entry url is what gets stored.

The Hong Kong and Taiwan channels that iptv-org tags [Geo-blocked] answer 403 from Korea: HOY, TVBS新聞, 東森新聞, 東森財經新聞, 華視新聞 and RTHK 32. Those streams are alive, they simply refuse this egress, and they would very likely play from a Hong Kong or Taiwan address.

CNN and CNN International have no usable url. The only turnerlive address in these playlists points at cnn_slate, the standby card, which the brief rules out, and the real feed gates its segments behind a cable-provider token. CNN sits on iptv-org's blocklist for the same reason, so there is nothing free to fall back on.


The router proxy filters some destinations itself. Instead of failing the connection it answers with a 41-byte page reading "the content is not available in your area", sometimes under HTTP 200 and sometimes under a 301 that redirects onto itself. The same body comes back from unrelated origins, a CCTV mirror on 74.91.26.218 and bloomberg.com among them, which is how we know it is injected rather than sent by the stream. A plain status-code check would have accepted these; the segment-size rule is what catches them.

The BBC CMAF/DASH manifests on vs-cmaf-*.akamaized.net cannot pass the non-HLS test by construction, since the manifest is a few kilobytes of XML rather than media. BBC News still passes on its HLS urls.

ABC News Live publishes ten numbered feeds on abcnews-streams.akamaized.net; the master playlist loads but its variants answer 404 from here, so the channel is listed as not reachable rather than missing.

The mirror farm that carries most of the working CCTV feeds throttles when several of its channels are pulled at once, which showed up as timeouts and stray 302s. Requests are therefore round-robined across hosts and a transient failure is retried once.

A url now has to prove it carries video. Either the body is a real playlist and a media segment of at least fifty kilobytes came back, or ffprobe has to name a codec. The earlier rule accepted any non-playlist response over fifty kilobytes, which let YouTube watch pages and GitHub text files through: they are large and they answer 200, but ExoPlayer cannot open either. Those four hosts are now refused outright and the affected channels were dropped unless another url stood up.

Making ffprobe a gate meant loosening it first. Several of these CDNs name their segments .jpg or give them no extension at all, and ffmpeg refuses such a file by default even after it has detected mpegts inside, so the probe came back empty and the stream looked like it was not video. With -extension_picky 0 and the two allowed-extension options the same urls resolve to h264, which is how the jdshipin redirectors behind 凤凰, 無綫新聞台, 翡翠台 and ViuTV were confirmed rather than dropped. ffprobe has no -4 option, so that could not be set; the Mac has no public IPv6 route and reaches these hosts over v4 regardless.

HEVC or MPEG-2: 翡翠台, ESPN8 The Ocho, National Geographic Wild HD East, National Geographic HD East

体育, 卫视, 纪录片 and 港台综艺 are matched by pattern rather than from a roster, so they are ranked instead of curated and then cut to 体育 at 30, 卫视 at 30, 纪录片 at 20, 港台综艺 at 25 respectively. The three extra playlists that feed them, the iptv-org sports and documentary categories and the US country list, are fenced off from the four news groups, so adding them could not disturb channels that had already been tested.

Headers: Setanta Sports
