-- 기존 게시글 3개를 Supabase 로 옮긴다. SQL Editor 에서 한 번만 실행(다시 실행해도 src_key 중복이라 건너뜀).
insert into public.posts (date,title,summary,body,link,thumb,src_key,published,auto) values
  ('2025-09-25','제약업계를 위한 ‘CSO 신고제’ 시행규칙 개정안의 모든 것','CSO를 운영하는 모든 사업자가 CSO 신고제를 통해 법의 테두리 안으로 들어오게 되었습니다. 시행규칙 개정안의 내용을 살펴봅니다.','현재 CSO를 운영하는 모든 사업자들은 CSO 신고제를 통해 법의 테두리 안으로 들어오게 되었습니다.','https://jwunius.imweb.me/16/?q=YToxOntzOjEyOiJrZXl3b3JkX3R5cGUiO3M6MzoiYWxsIjt9&bmode=view&idx=167949316&t=board','assets/news_thumbnail_03_640x400.jpg','https://jwunius.imweb.me/16/?q=YToxOntzOjEyOiJrZXl3b3JkX3R5cGUiO3M6MzoiYWxsIjt9&bmode=view&idx=167949316&t=board',true,false),
  ('2025-09-25','코오롱·JW·신일제약, CSO 검토… 중견제약사 대세 될까','코오롱제약, JW중외제약, 신일제약이 영업 조직을 CSO 방식으로 전환했거나 검토 중이라는 보도를 소개합니다. 신일제약은 이미 시작한 것으로 알려졌습니다.','코오롱제약, JW중외제약, 신일제약이 영업 조직을 CSO 방식으로 전환했거나 검토 중이라는 보도를 소개합니다. 신일제약은 이미 시작한 것으로 알려졌습니다.

출처: 시사저널e','https://jwunius.imweb.me/16/?q=YToxOntzOjEyOiJrZXl3b3JkX3R5cGUiO3M6MzoiYWxsIjt9&bmode=view&idx=167949361&t=board','assets/news_thumbnail_02_640x400.jpg','https://jwunius.imweb.me/16/?q=YToxOntzOjEyOiJrZXl3b3JkX3R5cGUiO3M6MzoiYWxsIjt9&bmode=view&idx=167949361&t=board',true,false),
  ('2025-12-15','[CSO뉴스] 2025년 12월 제약 CSO 뉴스 동향','제네릭 약가 인하와 CSO 시장 재편, CSO 신고제와 지출보고서 의무화, 제약사의 CSO 활용 현황을 정리했습니다. 시장은 더 투명해지고 대형·전문 CSO 중심으로 재편될 전망입니다.','제네릭 약가 인하와 CSO 시장 재편, CSO 신고제와 지출보고서 의무화, 제약사의 CSO 활용 현황을 정리했습니다.

종합 전망: 시장은 더 투명해지고, 대형·전문 CSO 중심으로 재편될 것으로 보입니다.','https://jwunius.imweb.me/16/?q=YToxOntzOjEyOiJrZXl3b3JkX3R5cGUiO3M6MzoiYWxsIjt9&bmode=view&idx=169038657&t=board','assets/news_thumbnail_01_640x400.jpg','https://jwunius.imweb.me/16/?q=YToxOntzOjEyOiJrZXl3b3JkX3R5cGUiO3M6MzoiYWxsIjt9&bmode=view&idx=169038657&t=board',true,false)
on conflict (src_key) do nothing;
