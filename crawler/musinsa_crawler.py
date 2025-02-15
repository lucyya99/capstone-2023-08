import requests
from urllib.request import urlretrieve, Request, urlopen
import boto3
from bs4 import BeautifulSoup
import json
from utils import ClassificationModel

MUSINSA_URL = "https://www.musinsa.com/ranking/best?"
BUCKET = "application-list-img"
POST_URL = "http://35.84.85.252:8000/goods/send-result"
TMP_IMG_PATH = "/home/ubuntu/tmp/temp_img.jpg"

s3 = boto3.client('s3')

def crawl_image() :
    top_param = {"period" : "now",
                "age" : "ALL",
                "mainCategory" : "001",
                "page" : 1,
                "viewType" : "small"}
    response = requests.get(MUSINSA_URL, params=top_param)
    if response.status_code == 200:
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')
    else:
        raise Exception(f"Musinsa Request Failed. Status Code is {response.status_code}")

    # make list of detail page's url
    goods_rank_list = soup.select_one("form#goodsRankForm").select_one("ul#goodsRankList").select("li.li_box")
    
    goods_list = list()
    for element in goods_rank_list:
        goods_id = element['data-goods-no']
        url = element.select_one("div.list_img > a").attrs['href']
        temp_dict = {"goods_id" : goods_id,
                     "detail_page_url" : url}
        goods_list.append(temp_dict)

    goods_metadata = dict()

    weight_path = "/home/ubuntu/capstone-2023-08/crawler/model_weights.pth"
    model = ClassificationModel(weight_path)

    # get goods name and image url from each detail page
    for goods in goods_list:
        req = Request(goods["detail_page_url"], headers={"User-Agent" : "Mozilla/5.9"})
        html = urlopen(req).read()
        soup = BeautifulSoup(html, "html.parser")

        goods_id = goods["goods_id"]
        goods_info = soup.select_one("div.product-img > img")
        goods_name = goods_info.attrs["alt"].split(")")[1].strip()
        brand_name = goods_info.attrs["alt"].split("(")[0].strip()
        goods_img_url = goods_info.attrs["src"]

        # download img from img_url and upload img as "{id}.jpg" in s3
        urlretrieve("https:" + goods_img_url, TMP_IMG_PATH)

        try:
            if model.inference(TMP_IMG_PATH) == 1:
                s3.upload_file(TMP_IMG_PATH, BUCKET, f"musinsa-crawled-img/top/{goods_id}.jpg", ExtraArgs={'ContentType': "image/jpeg", 'ACL': "public-read"})

                metadata_dict = {"id" : goods_id,
                                    "goods_name" : goods_name,
                                    "brand_name" : brand_name,
                                    "s3_img_url" : f"https://{BUCKET}.s3.us-west-2.amazonaws.com/musinsa-crawled-img/top/{goods_id}.jpg",
                                    "detail_page_url" : goods['detail_page_url']
                        }
                goods_metadata[goods["goods_id"]] = metadata_dict
        except:
            continue

    # make result file as json and post to server
    result_json = json.dumps(goods_metadata, ensure_ascii=False)
    response = requests.post(POST_URL, data=result_json.encode('utf-8'))


if __name__ == '__main__' :
    crawling_result = crawl_image()

