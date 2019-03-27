# -*- coding: utf-8 -*-
# @Author: gunjianpan
# @Date:   2019-02-09 11:10:52
# @Last Modified by:   gunjianpan
# @Last Modified time: 2019-03-12 20:22:57

import argparse
import codecs
import datetime
import threading
import time
import re

from bs4 import BeautifulSoup
from datetime import datetime
from proxy.getproxy import GetFreeProxy
from utils.db import Db
from utils.utils import begin_time, get_html, end_time, changeCookie, get_json


class TitleViews(object):
    """
    update title views
    """

    def __init__(self):
        self.Db = Db("blog")
        self.requests = GetFreeProxy()
        self.local_views = {}
        self.title_map = {}
        self.title2slug = {}
        self.failured_map = {}
        self.zhihu_views = {}
        self.zhihu_id = {}
        self.jianshu_views = {}
        self.jianshu_id = {}
        self.csdn_views = {}
        self.csdn_id = {}
        self.exist_data = {}
        self.getTitleMap()
        self.insert_sql = '''INSERT INTO title_views(`title_name`, `local_views`, `zhihu_views`, `csdn_views`, `jianshu_views`, `zhihu_id`, `csdn_id`, `jianshu_id`) VALUES %s'''
        self.update_sql = '''REPLACE INTO title_views(`id`, `title_name`, `local_views`, `zhihu_views`, `csdn_views`, `jianshu_views`, `zhihu_id`, `csdn_id`, `jianshu_id`, `created_at`) VALUES %s'''
        self.new_day_sql = '''INSERT INTO page_views(`date`, `existed_views`, `existed_spider`) VALUES %s'''

    def loadLocalView(self):
        """
        load local view
        """
        with open("blog/data/google", 'r') as f:
            test = f.readlines()
        test = test[7:]
        for index in test:
            arr = index.split(',')
            slug = self.matchSlug(arr[0])
            if slug is None or slug not in self.title_map:
                continue
            print(slug + ' ' + str(arr[1]) + ' ' + arr[0])
            if slug in self.local_views:
                self.local_views[slug] += int(arr[1])
            else:
                self.local_views[slug] = int(arr[1])

    def getTitleMap(self):
        """
        get title map
        """
        with open('blog/data/slug', 'r') as f:
            slug = f.readlines()
        with open('blog/data/title', 'r') as f:
            title = f.readlines()
        self.title_map = {tempslug.split(
            '"')[1]: title[num].split('"')[1] for num, tempslug in enumerate(slug)}
        title2slug = {
            self.title_map[index]: index for index in self.title_map.keys()}
        noemoji_title = {self.filter_emoji(
            self.title_map[index]).replace('\u200d', ''): index for index in self.title_map.keys()}
        self.title2slug = {**noemoji_title, **title2slug}

    def matchSlug(self, pattern):
        """
        match slug
        """
        arr = re.search(r'\/([^\/]+).html', pattern)
        return None if arr is None else arr.group(1)

    def getZhihuView(self):
        with open('blog/data/cookie', 'r') as f:
            cookie = f.readline()
        changeCookie(cookie[:-1])
        url_basic = [
            'https://www.zhihu.com/api/v4/creator/content_statistics/',
            'articles?order_field=object_created&order_sort=descend&begin_date=2018-09-01&end_date=',
            datetime.now().strftime("%Y-%m-%d"),
            '&page_no='
        ]
        url = "".join(url_basic)
        json = self.get_request(url + '1', 1)
        if not json:
            return
        for index in json['data']:
            zhihu_title = index['title']
            zhihu_id = int(index['url_token'])
            zhihu_count = int(index['read_count'])

            if zhihu_title in self.title2slug:
                temp_slug = self.title2slug[zhihu_title]
                self.zhihu_id[temp_slug] = zhihu_id
                self.zhihu_views[temp_slug] = zhihu_count
            elif zhihu_id in self.zhihu_id_map:
                temp_slug = self.zhihu_id_map[zhihu_id]
                self.zhihu_id[temp_slug] = zhihu_id
                self.zhihu_views[temp_slug] = zhihu_count
            else:
                print(index['title'])

        for index in range(json['count'] // 10):
            print('zhihu', index)
            json = self.get_request(url + str(index + 2), 1)
            if not json:
                continue
            for index in json['data']:
                zhihu_title = index['title']
                zhihu_id = int(index['url_token'])
                zhihu_count = int(index['read_count'])

                if zhihu_title in self.title2slug:
                    temp_slug = self.title2slug[zhihu_title]
                    self.zhihu_id[temp_slug] = zhihu_id
                    self.zhihu_views[temp_slug] = zhihu_count
                elif zhihu_id in self.zhihu_id_map:
                    temp_slug = self.zhihu_id_map[zhihu_id]
                    self.zhihu_id[temp_slug] = zhihu_id
                    self.zhihu_views[temp_slug] = zhihu_count
                else:
                    print(index['title'])

    def get_request(self, url, types):

        result = get_json(url, {})

        if not result:
            if self.can_retry(url):
                self.get_request(url, types)
            return
        return result

    def get_request_v2(self, url, types):

        result = get_html(url, {})

        if not result or not len(result.find_all('div', class_='content')):
            if self.can_retry(url):
                self.get_request(url, types)
            return
        return result

    def get_request_v3(self, url, types):

        result = get_html(url, {})

        if result is None or not result or not len(result.find_all('p', class_='content')):
            if self.can_retry(url):
                self.get_request(url, types)
            return
        return result

    def can_retry(self, url):
        """
        judge can retry once
        """
        if url not in self.failured_map:
            self.failured_map[url] = 0
            return True
        elif self.failured_map[url] < 2:
            self.failured_map[url] += 1
            return True
        else:
            print("Failured " + url)
            self.requests.log_write(url)
            self.failured_map[url] = 0
            return False

    def getJianshuViews(self):
        """
        get jianshu views
        """

        basic_url = 'https://www.jianshu.com/u/2e0f69e4a4f0'

        for rounds in range(1, 4):
            url = basic_url if rounds == 1 else basic_url + \
                '?order_by=shared_at&page=' + str(rounds)
            print(url)
            html = self.get_request_v2(url, 0)
            if html is None:
                print('None')
                return
            for index in html.find_all('li', class_=["", 'have-img']):
                if len(index.find_all('i')) < 3:
                    continue
                title = index.find_all('a', class_='title')[
                    0].text.replace('`', '')
                jianshu_id = int(index['data-note-id'])
                jianshu_count = int(index.find_all('a')[-2].text)
                if title in self.title2slug:
                    temp_slug = self.title2slug[title]
                    self.jianshu_id[temp_slug] = jianshu_id
                    self.jianshu_views[temp_slug] = jianshu_count
                elif jianshu_id in self.jianshu_id_map:
                    temp_slug = self.jianshu_id_map[jianshu_id]
                    self.jianshu_id[temp_slug] = jianshu_id
                    self.jianshu_views[temp_slug] = jianshu_count
                else:
                    print(title)

    def getCsdnViews(self):
        """
        get csdn views
        """

        basic_url = "https://blog.csdn.net/iofu728"

        for index in range(1, 3):
            url = basic_url if index == 1 else basic_url + \
                '/article/list/' + str(index) + '?'

            html = self.get_request_v3(url, 0)
            if html is None:
                print('None')
                return
            for div_lists in html.find_all('div', class_='article-item-box csdn-tracking-statistics'):
                if 'style' in div_lists.attrs:
                    continue
                csdn_id = int(div_lists['data-articleid'])
                title = div_lists.a.contents[2].replace(
                    '\n', '').strip().replace('`', '')
                csdn_count = int(div_lists.find_all(
                    'span', class_='read-num')[0].span.text)
                if title in self.title2slug:
                    temp_slug = self.title2slug[title]
                    self.csdn_id[temp_slug] = csdn_id
                    self.csdn_views[temp_slug] = csdn_count
                elif csdn_id in self.csdn_id_map:
                    temp_slug = self.csdn_id_map[csdn_id]
                    self.csdn_id[temp_slug] = csdn_id
                    self.csdn_views[temp_slug] = csdn_count
                else:
                    print(title)

    def filter_emoji(self, desstr, restr=''):
        '''
        filter emoji
        '''
        desstr = str(desstr)
        try:
            co = re.compile(u'[\U00010000-\U0010ffff]')
        except re.error:
            co = re.compile(u'[\uD800-\uDBFF][\uDC00-\uDFFF]')
        return co.sub(restr, desstr)

    def init_db(self):
        self.loadLocalView()
        self.getZhihuView()
        self.getJianshuViews()
        self.getCsdnViews()
        insert_list = []
        for index in self.title_map.keys():
            insert_list.append((index, self.local_views[index] if index in self.local_views else 0, self.zhihu_views[index] if index in self.zhihu_views else 0, self.csdn_views[index] if index in self.csdn_views else 0, self.jianshu_views[index]
                                if index in self.jianshu_views else 0, self.zhihu_id[index] if index in self.zhihu_id else 0, self.csdn_id[index] if index in self.csdn_id else 0, self.jianshu_id[index] if index in self.jianshu_id else 0))
        # return insert_list
        results = self.Db.insert_db(self.insert_sql % str(insert_list)[1:-1])
        if results:
            if len(insert_list):
                print('Insert ' + str(len(insert_list)) + ' Success!')
        else:
            pass

    def select_all(self):
        result = self.Db.select_db(
            "SELECT `id`, `title_name`, `local_views`, `zhihu_views`, `csdn_views`, `jianshu_views`, `zhihu_id`, `csdn_id`, `jianshu_id`, `created_at` from title_views where `is_deleted`=0")
        if result == False:
            print("SELECT Error!")
        else:
            self.exist_data = {index[1]: list(index) for index in result}
            self.zhihu_id_map = {index[6]: index[1]
                                 for index in result if index[6]}
            self.csdn_id_map = {index[7]: index[1]
                                for index in result if index[7]}
            self.jianshu_id_map = {index[8]: index[1]
                                   for index in result if index[8]}
            for index in self.exist_data:
                self.exist_data[index][-1] = self.exist_data[index][-1].strftime(
                    '%Y-%m-%d %H:%M:%S')

    def update_view(self):
        wait_map = {}
        self.select_all()
        self.getZhihuView()
        self.getJianshuViews()
        self.getCsdnViews()
        for index in self.zhihu_views.keys():
            if self.zhihu_views[index] == self.exist_data[index][3] and self.zhihu_id[index] == self.exist_data[index][6]:
                continue
            wait_map[index] = self.exist_data[index]
            wait_map[index][3] = self.zhihu_views[index]
            wait_map[index][6] = self.zhihu_id[index]
        for index in self.csdn_views.keys():
            if self.csdn_views[index] == self.exist_data[index][4] and self.csdn_id[index] == self.exist_data[index][7]:
                continue
            if index not in wait_map:
                wait_map[index] = self.exist_data[index]
            wait_map[index][4] = self.csdn_views[index]
            wait_map[index][7] = self.csdn_id[index]
        for index in self.jianshu_views.keys():
            if self.jianshu_views[index] == self.exist_data[index][5] and self.jianshu_id[index] == self.exist_data[index][8]:
                continue
            wait_map[index] = self.exist_data[index]
            wait_map[index][5] = self.jianshu_views[index]
            wait_map[index][8] = self.jianshu_id[index]
        update_list = [tuple(index) for index in wait_map.values()]
        # return update_list:q
        if not len(update_list):
            return
        results = self.Db.update_db(self.update_sql % str(update_list)[1:-1])
        if results:
            if len(update_list):
                print('Update ' + str(len(update_list)) + ' Success!')
        else:
            pass

    def new_day(self):
        day_data = self.Db.select_db(
            "SELECT `today_views`, `existed_views` from page_views order by `id` desc limit 1")
        with open("../blog/log/basic", 'r') as f:
            existed_spider = int(f.readlines()[1])
        today_date = datetime.datetime.now().strftime('%Y-%m-%d')
        new_day_list = [(today_date, day_data[0][0] +
                         day_data[0][1], existed_spider)]
        results = self.Db.insert_db(self.new_day_sql % str(new_day_list)[1:-1])
        if results:
            if len(new_day_list):
                print('New day update' + str(len(new_day_list)) + ' Success!')
        else:
            pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='gunjianpan blog backup code')
    parser.add_argument('--model', type=int, default=1, metavar='N',
                        help='model update or new day')
    model = parser.parse_args().model
    bb = TitleViews()
    if model == 1:
        bb.update_view()
    else:
        bb.new_day()
        bb.update_view()