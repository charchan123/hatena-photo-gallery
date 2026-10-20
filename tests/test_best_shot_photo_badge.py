from bs4 import BeautifulSoup
from best_shot_ui import _card

def test_only_monthly_badge_moves_into_existing_photo_link():
    row={'selection_id':'s','src':'https://example.test/a.jpg','gallery_name':'きのこ','capture_date':'2025-10-01','location':None,'comment':'コメント','annual_comment':None,'article_url':'https://example.test/day','article_title':'記事','is_annual_best':True}
    monthly=BeautifulSoup(_card(row),'html.parser')
    assert monthly.select_one('.best-shot-photo .best-shot-badge')
    assert not monthly.select('.best-shot-card__body .best-shot-badge')
    assert monthly.select_one('.best-shot-photo')['href']==row['src']
    hero=BeautifulSoup(_card(row,hero=True),'html.parser')
    assert hero.select_one('.best-shot-card__body .best-shot-badge')
    assert not hero.select('.best-shot-photo .best-shot-badge')
    row['is_annual_best']=False
    assert not BeautifulSoup(_card(row),'html.parser').select('.best-shot-badge')
