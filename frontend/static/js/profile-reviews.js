(() => {
  "use strict";

  const section = document.querySelector("[data-profile-reviews]");
  if (!section) return;

  const summaryEl = document.querySelector("[data-review-summary]");
  const countEl = section.querySelector("[data-review-count]");
  const statusEl = section.querySelector("[data-review-status]");
  const errorBox = section.querySelector("[data-review-error]");
  const errorMsg = section.querySelector("[data-review-error-message]");
  const retryBtn = section.querySelector("[data-review-retry]");
  const listEl = section.querySelector("[data-review-list]");
  const paginationBox = section.querySelector("[data-review-pagination]");
  const prevBtn = section.querySelector("[data-review-prev]");
  const nextBtn = section.querySelector("[data-review-next]");
  const pageLabel = section.querySelector("[data-review-page-label]");

  const pathMatch = window.location.pathname.match(/\/users\/(\d+)\/?/);
  const userId = section.dataset.userId || (pathMatch ? pathMatch[1] : "");
  if (!userId) return;

  const pageSize = 10;
  let currentPage = 1;
  let totalPages = 1;
  let activeRequest = 0;

  function formatStars(rating) {
    const score = Math.max(0, Math.min(5, Math.round(Number(rating) || 0)));
    return `${"★".repeat(score)}${"☆".repeat(5 - score)} (${score}/5)`;
  }

  function formatDate(iso) {
    if (!iso) return "";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "";
    return new Intl.DateTimeFormat("th-TH", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Asia/Bangkok",
    }).format(date);
  }

  function renderSummary(averageRating, reviewCount) {
    const count = Number(reviewCount) || 0;
    if (countEl) {
      countEl.textContent = `${count} รีวิว`;
    }
    if (!summaryEl) return;

    if (averageRating === null || averageRating === undefined || count === 0) {
      summaryEl.textContent = "ยังไม่มีคะแนนรีวิว";
      summaryEl.className = "profile-empty";
      return;
    }

    const avg = Number(averageRating);
    if (Number.isNaN(avg)) {
      summaryEl.textContent = "ยังไม่มีคะแนนรีวิว";
      summaryEl.className = "profile-empty";
      return;
    }

    summaryEl.textContent = `★ ${avg.toFixed(1)} / 5 (${count} รีวิว)`;
    summaryEl.className = "profile-credit-value";
  }

  function buildReviewItem(item) {
    const article = document.createElement("article");
    article.className = "review-item";

    const header = document.createElement("div");
    header.className = "review-item-header";

    const reviewer = document.createElement("span");
    reviewer.className = "review-reviewer";
    const reviewerName =
      item.reviewer?.display_name ||
      item.reviewer_display_name ||
      item.reviewer_name ||
      "ผู้ร่วมกิจกรรม";
    reviewer.textContent = reviewerName;

    const stars = document.createElement("span");
    stars.className = "review-stars";
    stars.textContent = formatStars(item.rating);

    header.append(reviewer, stars);
    article.append(header);

    const commentText = (item.comment || "").trim();
    if (commentText) {
      const comment = document.createElement("p");
      comment.className = "review-comment";
      comment.textContent = commentText;
      article.append(comment);
    }

    const metaParts = [];
    if (item.party?.title || item.party_title) {
      metaParts.push(`กิจกรรม: ${item.party?.title || item.party_title}`);
    }
    const createdText = formatDate(item.created_at);
    if (createdText) {
      metaParts.push(createdText);
    }
    if (metaParts.length) {
      const meta = document.createElement("div");
      meta.className = "review-meta";
      meta.textContent = metaParts.join(" · ");
      article.append(meta);
    }

    return article;
  }

  function extractReviewPayload(response) {
    const root = response || {};
    const data = root.data !== undefined ? root.data : root;

    const items = Array.isArray(data)
      ? data
      : Array.isArray(data?.reviews)
      ? data.reviews
      : Array.isArray(data?.items)
      ? data.items
      : Array.isArray(root?.reviews)
      ? root.reviews
      : [];

    const summaryObj = data?.summary || root?.summary || {};
    const averageRating =
      summaryObj.average_rating ??
      summaryObj.average ??
      data?.average_rating ??
      root?.average_rating ??
      null;

    const total =
      root.total ??
      data?.total ??
      summaryObj.review_count ??
      summaryObj.count ??
      data?.review_count ??
      root?.review_count ??
      items.length;

    const page = root.page ?? data?.page ?? currentPage;
    const size = root.page_size ?? data?.page_size ?? pageSize;

    return { items, averageRating, total: Number(total) || 0, page: Number(page) || 1, size: Number(size) || pageSize };
  }

  async function loadReviews(pageNumber) {
    const requestId = ++activeRequest;
    statusEl.hidden = false;
    statusEl.textContent = "กำลังโหลดรีวิว...";
    errorBox.hidden = true;
    listEl.hidden = true;
    paginationBox.hidden = true;

    try {
      const requestFn = window.UniSport?.request;
      if (typeof requestFn !== "function") {
        throw new Error("ไม่พบตัวเชื่อมต่อ API");
      }

      const response = await requestFn(
        `/users/${userId}/reviews?page=${pageNumber}&page_size=${pageSize}`,
        undefined,
        true
      );
      if (requestId !== activeRequest) return;

      const { items, averageRating, total, page, size } = extractReviewPayload(response);
      currentPage = page;
      totalPages = Math.max(1, Math.ceil(total / size));

      renderSummary(averageRating, total);

      if (!items.length) {
        statusEl.hidden = false;
        statusEl.textContent = "ยังไม่มีรีวิวสำหรับผู้ใช้นี้";
        listEl.replaceChildren();
      } else {
        statusEl.hidden = true;
        listEl.replaceChildren(...items.map(buildReviewItem));
        listEl.hidden = false;
      }

      if (total > size) {
        paginationBox.hidden = false;
        pageLabel.textContent = `หน้า ${currentPage} จาก ${totalPages}`;
        prevBtn.disabled = currentPage <= 1;
        nextBtn.disabled = currentPage >= totalPages;
      }
    } catch (error) {
      if (requestId !== activeRequest) return;
      statusEl.hidden = true;
      listEl.hidden = true;
      paginationBox.hidden = true;
      errorBox.hidden = false;
      errorMsg.textContent = error.status
        ? error.message
        : "ไม่สามารถโหลดข้อมูลรีวิวได้ กรุณาลองใหม่อีกครั้ง";
      if (summaryEl) {
        summaryEl.textContent = "โหลดคะแนนไม่สำเร็จ";
        summaryEl.className = "profile-empty";
      }
    }
  }

  prevBtn?.addEventListener("click", () => {
    if (currentPage > 1) loadReviews(currentPage - 1);
  });

  nextBtn?.addEventListener("click", () => {
    if (currentPage < totalPages) loadReviews(currentPage + 1);
  });

  retryBtn?.addEventListener("click", () => {
    loadReviews(currentPage);
  });

  loadReviews(1);
})();