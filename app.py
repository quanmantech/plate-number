"""车牌钥匙扣 STL 生成 — Flask Web 应用。"""

import io
import os
from urllib.parse import quote

from flask import Flask, render_template, request, send_file, jsonify, Response

from generator import generate_keychain_to_buffer, ModelGenerationError
from generator.batch_jobs import create_batch_job, get_batch_job, remove_batch_job
from generator.text_utils import normalize_custom_text

app = Flask(__name__)

ALLOWED_EXCEL_EXTENSIONS = {".xlsx", ".xlsm", ".xltx", ".xltm"}


def _attachment_response(data: bytes, filename: str, mimetype: str) -> Response:
    """返回附件响应，正确编码中文文件名。"""
    ascii_fallback = filename.encode("ascii", "ignore").decode() or "download"
    encoded = quote(filename, safe="")
    disposition = (
        f"attachment; filename=\"{ascii_fallback}\"; "
        f"filename*=UTF-8''{encoded}"
    )
    return Response(
        data,
        mimetype=mimetype,
        headers={"Content-Disposition": disposition},
    )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json(silent=True) or {}
    main_text = (data.get("main_text") or request.form.get("main_text", ""))
    side_text = (data.get("side_text") or request.form.get("side_text", ""))

    try:
        main_text = normalize_custom_text(main_text)
        side_text = normalize_custom_text(side_text, allow_empty=True)
    except ModelGenerationError as e:
        return jsonify({"error": str(e)}), 400

    try:
        buf = generate_keychain_to_buffer(main_text, side_text)
    except ModelGenerationError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        app.logger.exception("生成模型失败")
        return jsonify({"error": "生成模型时发生内部错误，请查看服务器日志"}), 500

    filename = f"keychain_{main_text.upper()}"
    if side_text:
        filename += f"_{side_text.upper()}"
    filename += ".stl"

    return send_file(
        buf,
        mimetype="model/stl",
        as_attachment=True,
        download_name=filename,
    )


@app.route("/api/batch-generate", methods=["POST"])
def api_batch_generate():
    """上传 Excel 并启动后台批量生成任务。"""
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify({"error": "请上传 Excel 文件"}), 400

    ext = os.path.splitext(upload.filename)[1].lower()
    if ext not in ALLOWED_EXCEL_EXTENSIONS:
        return jsonify({"error": "仅支持 .xlsx 格式的 Excel 文件"}), 400

    job_id = create_batch_job(upload.read())
    return jsonify({"job_id": job_id})


@app.route("/api/batch-progress/<job_id>")
def api_batch_progress(job_id: str):
    """查询批量生成进度。"""
    job = get_batch_job(job_id)
    if job is None:
        return jsonify({"error": "任务不存在或已过期"}), 404

    percent = 0
    if job.total > 0:
        percent = min(100, round(job.current / job.total * 100))

    return jsonify({
        "status": job.status,
        "current": job.current,
        "total": job.total,
        "percent": percent,
        "message": job.message,
        "zip_name": job.zip_name if job.status == "done" else None,
        "error": job.error,
    })


@app.route("/api/batch-download/<job_id>")
def api_batch_download(job_id: str):
    """下载批量生成完成的 ZIP 文件。"""
    job = get_batch_job(job_id)
    if job is None:
        return jsonify({"error": "任务不存在或已过期"}), 404
    if job.status != "done" or not job.zip_bytes:
        return jsonify({"error": "文件尚未生成完成"}), 400

    zip_name = job.zip_name or "双色车牌.zip"
    zip_bytes = job.zip_bytes
    remove_batch_job(job_id)

    return _attachment_response(zip_bytes, zip_name, "application/zip")


if __name__ == "__main__":
    # Windows 下 debug 重载器与 CadQuery/OCP 冲突，会导致页面 500
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="127.0.0.1", port=port, use_reloader=False)
