"""정적 분석 + 렌더링 채점기 — DEFECTS.md 68건 중 정적 22건 + 렌더링 10건, 총 32건.

20건은 `page.evaluate(_RULES_JS)` 한 번의 DOM/CSS 스냅샷(1280px)으로 잡는다.
D-09(포커스 링 제거)와 D-41(스킵 링크 없음)은 실제 키보드 포커스 이동이 있어야
드러나서 `_tab_checks()`가 Playwright의 `page.keyboard.press("Tab")`(진짜
브라우저 레벨 입력)로 따로 잡는다 — JS로 합성 KeyboardEvent를 쏘는 건 네이티브
탭 순회를 흉내 내지 못한다.

렌더링 티어 10건 중 7건(D-14/D-15/D-23/D-31/D-32/D-42/D-54)은 같은 1280px에서
`_RENDER_RULES_JS`로 잡는다 — 정적 스냅샷과 달리 요소 하나만 보는 게 아니라
두 요소(또는 요소와 기준값)의 렌더링 결과를 서로 비교해야 해서 규칙을 따로
뺐다. 나머지 3건(D-02/D-29/D-30)은 375px로 뷰포트를 좁혀야만 드러나서
`_VIEWPORT_RULES_JS`로 잡는다.

이건 "아무 사이트나 훑는 범용 접근성 스캐너"가 아니다. `ux-testbed/DEFECTS.md`에
이미 적힌 정확한 위치·수치(`.cart-link` 22×16px, `.chk` 10×10px 등)를 직접 겨눈
규칙이다 — 이 채점기의 목적 자체가 "이 도구가 이 정답지를 얼마나 잡아내는가"를
재는 것이라, 정답지를 알고 짜는 게 정직한 접근이다.

대비 계산 공식은 `agent-ux/uxagent/snapshot.py`의 `contrastOf`와 같은 WCAG 공식을
그대로 옮겼다 — 같은 대비를 두 곳에서 다르게 재면 숫자가 어긋난다.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import scoring
from .models import Defect, Finding, FindingMatch, Run, RunScore, SiteVariant

# 정해진 페이지 6장. CSS는 사이트 전체가 공유하므로, 규칙은 페이지 구분 없이
# 전부 돌리고 그 페이지에 있는 셀렉터만 자연히 걸린다.
PAGES = ["index.html", "list.html", "product.html?id=1", "cart.html", "checkout.html", "complete.html"]

# 페이지 하나에서 20개 규칙을 전부 검사해 [{code, note}] 를 돌려주는 스크립트.
_RULES_JS = r"""
() => {
  const hits = [];
  const add = (code, note) => hits.push({code, note});

  /* ── 대비: agent-ux/uxagent/snapshot.py 의 contrastOf 와 같은 WCAG 공식 ── */
  const nums = (s) => (s.match(/[\d.]+/g) || []).map(Number);
  const isTransparent = (s) => { const n = nums(s); return n.length >= 4 && n[3] < 0.1; };
  const lum = (rgb) => {
    const a = rgb.slice(0, 3).map((v) => {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * a[0] + 0.7152 * a[1] + 0.0722 * a[2];
  };
  const ratio = (a, b) => {
    const L1 = lum(a), L2 = lum(b);
    return (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
  };
  const effectiveBg = (el) => {
    let n = el;
    while (n && n.nodeType === 1) {
      const bg = getComputedStyle(n).backgroundColor;
      if (bg && !isTransparent(bg)) { const v = nums(bg); if (v.length >= 3) return v; }
      n = n.parentElement;
    }
    return [255, 255, 255];
  };
  const contrastOf = (el) => {
    try {
      const fg = nums(getComputedStyle(el).color);
      if (fg.length < 3) return null;
      return Math.round(ratio(fg, effectiveBg(el)) * 10) / 10;
    } catch (e) { return null; }
  };

  const bodyC = contrastOf(document.body);
  if (bodyC !== null && bodyC < 4.5) add("D-05", `본문 대비 ${bodyC}:1`);

  const topbar = document.querySelector(".topbar");
  if (topbar) { const c = contrastOf(topbar); if (c !== null && c < 4.5) add("D-05b", `상단바 대비 ${c}:1`); }

  const footerP = document.querySelector(".footer p");
  if (footerP) { const c = contrastOf(footerP); if (c !== null && c < 4.5) add("D-27", `푸터 대비 ${c}:1`); }

  /* ── 폰트 크기 · 행간 ── */
  const bodyFont = parseFloat(getComputedStyle(document.body).fontSize) || 0;
  if (bodyFont && bodyFont < 12) add("D-06", `본문 폰트 ${bodyFont}px`);

  const bodyLH = parseFloat(getComputedStyle(document.body).lineHeight) || 0;
  if (bodyFont && bodyLH && bodyLH / bodyFont < 1.3) {
    add("D-07", `행간 비율 ${(bodyLH / bodyFont).toFixed(2)}`);
  }

  /* ── 라벨 없는 폼 ── */
  if (document.querySelectorAll("input, select, textarea").length > 0
      && document.querySelectorAll("label").length === 0) {
    add("D-08", "입력 필드는 있는데 label이 하나도 없음");
  }

  /* ── 클릭형인데 role/tabindex 없는 요소 (가짜 버튼) ── */
  document.querySelectorAll(".fake-btn, div[onclick], span[onclick]").forEach((el) => {
    if (!el.getAttribute("role") && !el.hasAttribute("tabindex")) {
      add("D-10", `${el.className || el.tagName} — role/tabindex 없음`);
    }
  });

  /* ── 터치 타깃 24×24 미만 (WCAG 2.2 Target Size Minimum) ── */
  const targetCheck = (sel, code) => {
    document.querySelectorAll(sel).forEach((el) => {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0 && (r.width < 24 || r.height < 24)) {
        add(code, `${sel} ${Math.round(r.width)}x${Math.round(r.height)}px`);
      }
    });
  };
  targetCheck(".cart-link", "D-11");
  targetCheck(".nav a", "D-04");
  targetCheck(".btn", "D-12");
  targetCheck(".opt", "D-19");
  targetCheck(".qty button", "D-21");
  targetCheck(".chk", "D-24");

  /* ── 뷰포트 메타 태그 ── */
  if (!document.querySelector('meta[name="viewport"]')) add("D-28", "meta viewport 없음");

  /* ── alt 없는 이미지 ── */
  const imgs = document.querySelectorAll("img");
  const noAlt = Array.from(imgs).filter((img) => !img.getAttribute("alt")).length;
  if (imgs.length > 0 && noAlt === imgs.length) add("D-37", `이미지 ${noAlt}개 alt 없음`);

  /* ── 언어 속성 ── */
  const lang = document.documentElement.getAttribute("lang");
  if (lang !== "ko") add("D-38", `lang="${lang}"`);

  /* ── main 랜드마크 ── */
  if (!document.querySelector("main")) add("D-39", "<main> 랜드마크 없음");

  /* ── 페이지 제목 · 설명 ── */
  const desc = document.querySelector('meta[name="description"]');
  if (document.title === "쇼핑몰" && !desc) add("D-40", "title이 고정값 + description 없음");

  /* ── 목록 페이지 h1 (다른 페이지엔 h1이 없어도 정상일 수 있어 경로로 제한) ── */
  if (location.pathname.includes("list.html") && !document.querySelector("h1")) {
    add("D-48", "list.html에 h1 없음");
  }

  /* ── 수량 버튼의 접근 가능한 이름 (기호 한 글자뿐이면 부족하다고 본다) ── */
  document.querySelectorAll(".qty button").forEach((el) => {
    const text = (el.innerText || "").trim();
    if (!el.getAttribute("aria-label") && text.length <= 1) {
      add("D-53", `qty 버튼 이름이 "${text}" 뿐`);
    }
  });

  return hits;
}
"""

# 렌더링 티어 7건 — 1280px에서 요소 하나가 아니라 두 요소(또는 요소와 기준값)를
# 서로 비교해야 잡히는 것들.
_RENDER_RULES_JS = r"""
() => {
  const hits = [];
  const add = (code, note) => hits.push({code, note});

  const nums = (s) => (s.match(/[\d.]+/g) || []).map(Number);
  const lum = (rgb) => {
    const a = rgb.slice(0, 3).map((v) => {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * a[0] + 0.7152 * a[1] + 0.0722 * a[2];
  };

  const bodyFont = parseFloat(getComputedStyle(document.body).fontSize) || 0;

  /* ── D-14: 비활성 버튼이 활성 버튼과 시각적으로 동일 ── */
  document.querySelectorAll('.btn[disabled], .btn[aria-disabled="true"]').forEach((el) => {
    const cs = getComputedStyle(el);
    const opacity = parseFloat(cs.opacity);
    if (cs.cursor !== "not-allowed" && opacity >= 0.9) {
      add("D-14", `disabled 버튼인데 cursor=${cs.cursor}, opacity=${opacity}`);
    }
  });

  /* ── D-15: 카드 간 간격이 좁아 경계가 불분명 ── */
  const grid = document.querySelector(".grid");
  if (grid && grid.children.length > 1) {
    const gap = parseFloat(getComputedStyle(grid).columnGap) || 0;
    if (gap < 8) add("D-15", `.grid columnGap ${gap}px`);
  }

  /* ── D-23: placeholder가 입력값보다 진해 이미 입력된 것처럼 보임 ── */
  document.querySelectorAll("input[placeholder], textarea[placeholder]").forEach((el) => {
    const textColor = nums(getComputedStyle(el).color);
    let placeholderColor = [];
    try { placeholderColor = nums(getComputedStyle(el, "::placeholder").color); } catch (e) { /* noop */ }
    if (textColor.length >= 3 && placeholderColor.length >= 3 && lum(placeholderColor) < lum(textColor)) {
      add("D-23", "placeholder가 입력값보다 어두움(진함)");
    }
  });

  /* ── D-31: 아무 스타일도 안 받은 '순수' 링크가 본문과 같은 색 + 밑줄 없음 ──
     nav/cart-link/btn처럼 이미 자기 스타일이 있는 링크는 제외한다 — 그런
     링크는 (터치 타깃 등) 자기 결함이 따로 있고, 여기서 보는 건 일반 `a`
     규칙 하나로만 스타일이 정해지는 링크(주로 푸터)가 본문과 안 섞이는지다. */
  const bodyColor = nums(getComputedStyle(document.body).color);
  const plainLinks = Array.from(document.querySelectorAll("a")).filter((a) => {
    const r = a.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return false;
    if (a.closest(".nav")) return false;
    if (a.classList.contains("cart-link") || a.classList.contains("btn")) return false;
    return true;
  });
  if (plainLinks.length > 0 && bodyColor.length >= 3) {
    const indistinct = plainLinks.filter((a) => {
      const cs = getComputedStyle(a);
      const c = nums(cs.color);
      if (c.length < 3) return false;
      const sameColor = [0, 1, 2].every((i) => Math.abs(c[i] - bodyColor[i]) < 6);
      return sameColor && cs.textDecorationLine === "none";
    });
    if (indistinct.length === plainLinks.length) {
      add("D-31", "스타일 없는 링크가 본문 색과 같고 밑줄도 없음");
    }
  }

  /* ── D-32: h1이 본문 대비 충분히 크지 않음(위계 붕괴) ── */
  const heroH1 = document.querySelector(".hero h1, h1");
  if (heroH1 && bodyFont) {
    const h1Font = parseFloat(getComputedStyle(heroH1).fontSize) || 0;
    if (h1Font > 0 && h1Font < bodyFont * 1.5) {
      add("D-32", `h1 ${h1Font}px, 본문 ${bodyFont}px — 위계 차이가 거의 없음`);
    }
  }

  /* ── D-42: 헤딩 태그 없이 span으로 만든 섹션 제목 ── */
  document.querySelectorAll("span").forEach((el) => {
    const next = el.nextElementSibling;
    if (!next || !next.matches("ul, ol, .grid, [class*='grid']")) return;
    const fontSize = parseFloat(getComputedStyle(el).fontSize) || 0;
    if (fontSize > bodyFont) {
      add("D-42", `"${el.textContent.trim().slice(0, 20)}" — 헤딩 태그 없이 span으로 섹션 제목 표시`);
    }
  });

  /* ── D-54: 설명이 잘린 채 노출되고 펼칠 방법이 없음 ──
     scrollHeight가 clientHeight를 넘는지로만 보면, 특정 상품의 설명 글자 수가
     우연히 그 높이에 딱 맞아떨어질 때 놓친다 — 실제로 결함 CSS는 글자 수와
     무관하게 항상 낮은 고정 높이 + overflow:hidden이므로, 그 구조 자체를 본다. */
  document.querySelectorAll("div, p").forEach((el) => {
    const text = (el.textContent || "").trim();
    if (text.length < 60) return;
    const cs = getComputedStyle(el);
    if (cs.overflow !== "hidden" && cs.overflowY !== "hidden") return;
    const fixedHeight = parseFloat(cs.height) || 0;
    if (!fixedHeight || fixedHeight > 40) return;
    const next = el.nextElementSibling;
    const hasExpand = next && /더보기|펼치기|more/i.test(next.textContent || "");
    if (!hasExpand) {
      add("D-54", `설명이 ${fixedHeight}px 고정 높이 + overflow:hidden으로 잘릴 수 있음, 펼치기 없음`);
    }
  });

  return hits;
}
"""

# 뷰포트 티어 3건 — 375px로 좁혀야만 드러나는 것들. 호출부가 리사이즈 후에 돈다.
_VIEWPORT_RULES_JS = r"""
() => {
  const hits = [];
  const add = (code, note) => hits.push({code, note});

  /* ── D-29: 고정 폭 요소로 인한 가로 스크롤 ── */
  const scrollW = document.documentElement.scrollWidth;
  const clientW = document.documentElement.clientWidth;
  if (scrollW > clientW + 5) add("D-29", `scrollWidth ${scrollW}px > clientWidth ${clientW}px`);

  /* ── D-30: 좁은 화면에서도 고정 다열 그리드 유지 ── */
  const grid = document.querySelector(".grid");
  if (grid) {
    const cols = (getComputedStyle(grid).gridTemplateColumns || "").trim().split(/\s+/).filter(Boolean);
    if (cols.length >= 4) add("D-30", `375px에서도 grid-template-columns ${cols.length}열 고정`);
  }

  /* ── D-02: 햄버거 메뉴 없이 헤더 요소가 좁은 화면 밖으로 밀려남 ──
     .header에 overflow:hidden이 있어도, 형제 요소(.wrap 등)가 문서 전체를
     이미 뷰포트보다 넓게 만들어 버리면 .header 자신도 그 넓이를 따라가
     버려서 정작 아무것도 못 자른다 — nav는 flex로 왼쪽에 붙어 있어 안
     밀리지만, `.nav{margin-right:auto}`에 밀려 맨 오른쪽까지 가는
     `.cart-link`(장바구니)가 화면 밖으로 나가 도달 불가능해진다. 그래서
     .header 자기 경계가 아니라 '실제 눈에 보이는 뷰포트 폭'을 기준으로,
     nav 링크와 cart-link 둘 다 확인한다. */
  const hasToggle = !!document.querySelector(
    '.menu-toggle, [aria-label*="메뉴"], button[aria-expanded]'
  );
  if (!hasToggle) {
    const viewportW = window.innerWidth;
    const headerLinks = document.querySelectorAll(".nav a, .cart-link");
    const clipped = Array.from(headerLinks).some(
      (a) => a.getBoundingClientRect().right > viewportW + 2
    );
    if (clipped) add("D-02", "햄버거 메뉴 없이 헤더 요소가 좁은 화면 밖으로 밀려남");
  }

  return hits;
}
"""


async def _tab_checks(page) -> list[dict]:
    """D-41(스킵 링크) · D-09(포커스 링) — 진짜 Tab 입력이 있어야 잡힌다."""
    hits: list[dict] = []
    await page.evaluate("document.activeElement && document.activeElement.blur()")

    await page.keyboard.press("Tab")
    first = await page.evaluate(
        """() => {
          const el = document.activeElement;
          if (!el || el === document.body) return null;
          return { text: (el.innerText || el.textContent || '').trim(), href: el.getAttribute('href') || '' };
        }"""
    )
    is_skip_link = bool(first) and (
        any(word in (first["text"] or "").lower() for word in ["건너뛰기", "바로가기", "skip"])
        or (first["href"] or "").startswith("#main")
    )
    if not is_skip_link:
        hits.append({"code": "D-41", "note": "첫 Tab이 스킵 링크로 가지 않음"})

    # 이어서 몇 번 더 Tab을 눌러 어느 한 곳이라도 시각적 포커스 표시가 있는지 본다.
    # box-shadow로 대체한 사이트도 있어서 outline만 보면 오탐이 난다.
    visible_focus = False
    for _ in range(4):
        await page.keyboard.press("Tab")
        style = await page.evaluate(
            """() => {
              const el = document.activeElement;
              if (!el || el === document.body) return null;
              const cs = getComputedStyle(el);
              const outlineVisible = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0;
              const shadowVisible = !!cs.boxShadow && cs.boxShadow !== 'none';
              return { visible: outlineVisible || shadowVisible };
            }"""
        )
        if style and style["visible"]:
            visible_focus = True
            break
    if not visible_focus:
        hits.append({"code": "D-09", "note": "Tab 순회 중 어디서도 포커스 표시가 보이지 않음"})

    return hits


@dataclass
class ScanSummary:
    hits: int
    matched: int
    unmatched: int
    score: RunScore


async def scan_variant(base_url: str) -> list[dict]:
    """정해진 페이지 6장을 열어 규칙을 돌리고 {code, screen_key, note} 목록을 모은다."""
    from playwright.async_api import async_playwright

    root = base_url.rstrip("/")
    results: list[dict] = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            for path in PAGES:
                try:
                    await page.set_viewport_size({"width": 1280, "height": 800})
                    await page.goto(f"{root}/{path}", wait_until="domcontentloaded", timeout=15000)
                except Exception:  # noqa: BLE001 — 한 페이지가 없어도 나머지는 마저 돈다
                    continue
                hits = await page.evaluate(_RULES_JS)
                hits = hits + await page.evaluate(_RENDER_RULES_JS)
                hits = hits + await _tab_checks(page)

                # 375px는 항상 1280px 규칙들 다음에 — 순서를 바꾸면 좁은 화면
                # 기준으로 위 규칙들이 잘못 잡힌다.
                await page.set_viewport_size({"width": 375, "height": 800})
                hits = hits + await page.evaluate(_VIEWPORT_RULES_JS)

                for hit in hits:
                    results.append({
                        "code": hit["code"],
                        "screen_key": path,
                        "note": hit["note"],
                    })
        finally:
            await browser.close()
    return results


async def run_static_scan(session: Session, run_id: uuid.UUID) -> ScanSummary:
    """이 run이 가리키는 site_variant를 스캔해서 Finding/FindingMatch를 채운다."""
    run = session.get(Run, run_id)
    if run is None:
        raise ValueError(f"run {run_id} 없음")
    variant = session.get(SiteVariant, run.site_variant_id)

    defects_by_code = {
        d.code: d
        for d in session.scalars(select(Defect).where(Defect.project_id == variant.project_id))
    }

    hits = await scan_variant(variant.base_url)

    matched = 0
    unmatched = 0
    for hit in hits:
        finding = Finding(
            run_id=run_id,
            screen_key=hit["screen_key"],
            raw_text=f"{hit['code']}: {hit['note']}",
            scorer_version="static-v1",
        )
        session.add(finding)
        session.flush()  # finding.id 확보

        defect = defects_by_code.get(hit["code"])
        # clean/flawed 구분은 여기서 하지 않는다 — scoring.compute()가 이미
        # variant.is_control 이면 전부 오탐으로 뒤집어 계산하므로, 여기서는
        # "규칙이 이 결함 코드와 일치했다"는 사실만 true_positive로 남긴다.
        if defect is not None:
            session.add(FindingMatch(
                finding_id=finding.id, defect_id=defect.id,
                verdict="true_positive", matched_by="rule",
            ))
            matched += 1
        else:
            # 정답지가 아직 로드 안 된 프로젝트(seed 미실행) — 없는 걸 있는 척
            # 연결하지 않는다.
            session.add(FindingMatch(
                finding_id=finding.id, defect_id=None,
                verdict="unmatched", matched_by="rule",
            ))
            unmatched += 1

    score = scoring.persist(session, run_id, "static-v1")
    return ScanSummary(hits=len(hits), matched=matched, unmatched=unmatched, score=score)
