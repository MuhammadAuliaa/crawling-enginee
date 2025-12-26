from flask import Flask, render_template, request
from apify_client import ApifyClient
import os
from dotenv import load_dotenv
from flask import jsonify
from datetime import datetime
from flask import send_file
import pandas as pd
import tempfile

load_dotenv()

app = Flask(
    __name__,
    template_folder="app/templates",
    static_folder="app/static"
)

APIFY_TOKEN = os.getenv("APIFY_TOKEN")
INSTAGRAM_ACTOR_ID = "499mNnuVGkU2S5rh1"

client = ApifyClient(APIFY_TOKEN)

def format_timestamp(ts):
    try:
        # kalau ts dalam detik
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "-"
app.jinja_env.filters["format_ts"] = format_timestamp

@app.route("/crawling", methods=["GET"])
def crawling_page():
    return render_template("crawling.html")

@app.route("/crawl/start", methods=["POST"])
def start_crawl():
    platform = request.form.get("platform")
    url = request.form.get("url")
    limit = int(request.form.get("limit", 15))

    if platform != "instagram":
        return render_template(
            "crawling.html",
            error="Platform belum didukung"
        )

    run_input = {
        "postUrls": [url],
        "maxCommentsPerPost": limit,
    }

    run = client.actor(INSTAGRAM_ACTOR_ID).call(
        run_input=run_input
    )

    return render_template(
        "crawling.html",
        run_id=run["id"],
        platform=platform
    )

@app.route("/crawl/status/<run_id>")
def crawl_status(run_id):
    run = client.run(run_id).get()

    status = run["status"]
    dataset_id = run.get("defaultDatasetId")

    item_count = 0
    if status == "SUCCEEDED" and dataset_id:
        # hitung jumlah item di dataset
        dataset = client.dataset(dataset_id)
        item_count = dataset.get().get("itemCount", 0)

    return jsonify({
        "status": status,
        "item_count": item_count
    })

# def get_dataset_items(run_id, limit=500):
#     run = client.run(run_id).get()
#     dataset_id = run.get("defaultDatasetId")

#     if not dataset_id:
#         return []

#     dataset = client.dataset(dataset_id)
#     items = dataset.list_items(limit=limit).items

#     return items

def get_dataset_items(run_id, page=1, per_page=10):
    run = client.run(run_id).get()
    dataset_id = run.get("defaultDatasetId")

    if not dataset_id:
        return [], 0

    dataset = client.dataset(dataset_id)

    offset = (page - 1) * per_page

    result = dataset.list_items(
        limit=per_page,
        offset=offset
    )

    total_items = dataset.get().get("itemCount", 0)

    return result.items, total_items

# @app.route("/crawl/result/<run_id>")
# def crawl_result(run_id):
#     items = get_dataset_items(run_id)

#     return render_template(
#         "crawling.html",
#         crawl_results=items,
#         # run_id=run_id,
#         run_id=None,
#         platform="instagram"  # sementara hardcode

#     )

@app.route("/crawl/result/<run_id>")
def crawl_result(run_id):
    page = int(request.args.get("page", 1))
    per_page = 10

    items, total_items = get_dataset_items(
        run_id,
        page=page,
        per_page=per_page
    )

    total_pages = (total_items + per_page - 1) // per_page

    return render_template(
        "crawling.html",
        crawl_results=items,
        run_id=None,                 # stop spinner
        platform="instagram",
        page=page,
        total_pages=total_pages,
        run_id_result=run_id
    )

@app.route("/crawl/data/<run_id>")
def crawl_data(run_id):
    items = get_dataset_items(run_id)
    return jsonify(items)

def get_all_dataset_items(run_id, limit=5000):
    run = client.run(run_id).get()
    dataset_id = run.get("defaultDatasetId")

    if not dataset_id:
        return []

    dataset = client.dataset(dataset_id)

    items = dataset.list_items(
        limit=limit
    ).items

    return items

@app.route("/crawl/download/<run_id>")
def download_excel(run_id):
    items = get_all_dataset_items(run_id)

    if not items:
        return "No data", 400

    rows = []
    for item in items:
        rows.append({
            "Platform": "Instagram",
            "URL": item.get("postUrl"),
            "Username": item.get("ownerUsername"),
            "Komentar": item.get("text"),
            "Created At": item.get("timestamp")
        })

    df = pd.DataFrame(rows)

    import tempfile
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    df.to_excel(tmp.name, index=False)

    return send_file(
        tmp.name,
        as_attachment=True,
        download_name="instagram_crawling.xlsx"
    )

if __name__ == "__main__":
    app.run(debug=True)
