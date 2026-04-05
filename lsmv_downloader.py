"""
========================================================
 LSMV 자동 XML 다운로더
 ArisGlobal LifeSphere MultiVigilance (LSMV)
 케이스별 E2B XML 자동 다운로드 스크립트

 사용법:
   1. config.py 에서 URL, 계정 정보 입력
   2. pip install -r requirements.txt
   3. playwright install chromium
   4. python lsmv_downloader.py
========================================================
"""

import os
import re
import time
import logging
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

import config


# ============================================================
#  로거 설정
# ============================================================
def setup_logger():
    Path(config.LOG_DIR).mkdir(exist_ok=True)
    log_path = os.path.join(config.LOG_DIR, config.LOG_FILE)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


logger = setup_logger()


# ============================================================
#  LsmvDownloader 클래스
# ============================================================
class LsmvDownloader:

    def __init__(self):
        Path(config.DOWNLOAD_DIR).mkdir(exist_ok=True)
        self.playwright = None
        self.browser    = None
        self.context    = None
        self.page       = None

    # ----------------------------------------------------------
    #  브라우저 시작 / 종료
    # ----------------------------------------------------------
    def start_browser(self):
        logger.info("브라우저를 시작합니다...")
        self.playwright = sync_playwright().start()

        browser_launcher = getattr(self.playwright, config.BROWSER_TYPE)
        self.browser = browser_launcher.launch(headless=config.HEADLESS)

        # 다운로드 폴더 자동 지정
        self.context = self.browser.new_context(
            accept_downloads=True
        )
        self.context.set_default_timeout(config.TIMEOUT)
        self.page = self.context.new_page()
        logger.info("브라우저 시작 완료")

    def stop_browser(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        logger.info("브라우저를 종료했습니다.")

    # ----------------------------------------------------------
    #  로그인
    # ----------------------------------------------------------
    def login(self):
        logger.info(f"LSMV 접속 중: {config.LSMV_URL}")
        self.page.goto(config.LSMV_URL)

        if config.LOGIN_TYPE == "id_pw":
            self._login_id_pw()
        elif config.LOGIN_TYPE == "sso":
            self._login_sso()
        else:
            raise ValueError(f"알 수 없는 LOGIN_TYPE: {config.LOGIN_TYPE}")

    def _login_id_pw(self):
        """
        아이디/비밀번호 로그인
        ※ 사이트의 실제 셀렉터(selector)에 맞게 수정 필요
           - 아이디 입력창: input[name="username"] 또는 #username 등
           - 비번 입력창:   input[name="password"] 또는 #password 등
           - 로그인 버튼:   button[type="submit"] 또는 #loginBtn 등
        """
        logger.info("아이디/비밀번호 로그인 시도...")

        # ▼ 아래 셀렉터는 실제 LSMV 로그인 페이지에 맞게 수정하세요
        self.page.wait_for_selector("input[name='username']")
        self.page.fill("input[name='username']", config.USERNAME)
        self.page.fill("input[name='password']", config.PASSWORD)
        self.page.click("button[type='submit']")

        # 로그인 완료 대기 (메인 페이지 요소가 뜰 때까지)
        # ▼ 로그인 후 나타나는 요소의 셀렉터로 변경하세요
        self.page.wait_for_selector(".main-content, #dashboard, .worklist", timeout=15000)
        logger.info("로그인 성공!")

    def _login_sso(self):
        """
        SSO 로그인 (Microsoft 등)
        ※ SSO는 MFA(다중인증) 때문에 자동화가 어려울 수 있습니다.
           이 경우 수동으로 로그인 후 엔터를 누르도록 안내합니다.
        """
        logger.info("SSO 로그인 — 브라우저에서 직접 로그인해주세요...")
        logger.info("로그인 완료 후 이 터미널에서 Enter 키를 눌러주세요.")
        input("로그인 완료 후 Enter 키를 눌러주세요...")
        logger.info("SSO 로그인 완료로 간주하고 진행합니다.")

    # ----------------------------------------------------------
    #  케이스 목록 수집
    # ----------------------------------------------------------
    def get_all_case_ids(self):
        """
        LSMV 케이스 목록 페이지에서 전체 케이스 ID를 수집합니다.
        페이지네이션이 있으면 모든 페이지를 순회합니다.

        ※ 실제 LSMV UI의 셀렉터에 맞게 수정 필요
        """
        logger.info("케이스 목록을 수집합니다...")

        # ▼ 케이스 목록(Worklist) 페이지로 이동 — 실제 URL/경로로 변경
        worklist_url = f"{config.LSMV_URL}/worklist"
        self.page.goto(worklist_url)
        self.page.wait_for_load_state("networkidle")

        # 날짜 필터 적용
        if config.FILTER_DATE_FROM or config.FILTER_DATE_TO:
            self._apply_date_filter()

        all_case_ids = []
        page_num = 1

        while True:
            logger.info(f"  페이지 {page_num} 케이스 수집 중...")

            # ▼ 케이스 행(row) 셀렉터 — 실제 LSMV 테이블 구조에 맞게 수정
            self.page.wait_for_selector("table.case-table tbody tr, .case-row", timeout=10000)
            rows = self.page.query_selector_all("table.case-table tbody tr, .case-row")

            if not rows:
                logger.warning(f"  페이지 {page_num}에서 케이스를 찾지 못했습니다.")
                break

            for row in rows:
                # ▼ 케이스 ID를 담고 있는 셀 셀렉터로 변경
                case_id_el = row.query_selector("td.case-id, .case-number")
                if case_id_el:
                    case_id = case_id_el.inner_text().strip()
                    if case_id:
                        all_case_ids.append(case_id)

            logger.info(f"  페이지 {page_num}: {len(rows)}개 케이스 수집")

            # 다음 페이지 버튼 확인
            next_btn = self.page.query_selector("button.next-page:not([disabled]), a.next-page:not(.disabled)")
            if next_btn:
                next_btn.click()
                self.page.wait_for_load_state("networkidle")
                page_num += 1
            else:
                logger.info("  마지막 페이지입니다.")
                break

        logger.info(f"총 {len(all_case_ids)}개의 케이스를 수집했습니다.")
        return all_case_ids

    def _apply_date_filter(self):
        """날짜 필터 적용 — 실제 LSMV 필터 UI에 맞게 수정"""
        logger.info(f"날짜 필터 적용: {config.FILTER_DATE_FROM} ~ {config.FILTER_DATE_TO}")
        try:
            # ▼ 날짜 필터 입력창 셀렉터로 변경
            if config.FILTER_DATE_FROM:
                self.page.fill("input[name='dateFrom'], #filterDateFrom", config.FILTER_DATE_FROM)
            if config.FILTER_DATE_TO:
                self.page.fill("input[name='dateTo'], #filterDateTo", config.FILTER_DATE_TO)

            # ▼ 필터 적용 버튼 셀렉터로 변경
            self.page.click("button#applyFilter, button.apply-filter")
            self.page.wait_for_load_state("networkidle")
        except Exception as e:
            logger.warning(f"날짜 필터 적용 실패 (수동으로 확인 필요): {e}")

    # ----------------------------------------------------------
    #  케이스 상세 페이지 접속 & XML 다운로드
    # ----------------------------------------------------------
    def download_case_xml(self, case_id):
        """
        케이스 ID를 받아 해당 케이스의 E2B XML을 다운로드합니다.

        ※ 실제 LSMV의 케이스 상세 URL 패턴과 XML 내보내기 버튼에 맞게 수정 필요
        """
        save_path = os.path.join(config.DOWNLOAD_DIR, f"{case_id}.xml")

        # 이미 다운로드된 파일은 건너뜀
        if os.path.exists(save_path):
            logger.info(f"  [{case_id}] 이미 다운로드됨 — 건너뜁니다.")
            return True

        for attempt in range(1, config.RETRY_COUNT + 1):
            try:
                # ▼ 케이스 상세 페이지 URL 패턴으로 변경
                case_url = f"{config.LSMV_URL}/cases/{case_id}"
                self.page.goto(case_url)
                self.page.wait_for_load_state("networkidle")

                # ▼ XML 내보내기(Export) 버튼 셀렉터로 변경
                #    예: "Export E2B", "Download XML", "Export" 버튼 등
                export_btn = self.page.query_selector(
                    "button:has-text('Export E2B'), "
                    "button:has-text('XML'), "
                    "a:has-text('Export E2B'), "
                    "a:has-text('Download XML'), "
                    ".export-xml-btn"
                )

                if not export_btn:
                    logger.warning(f"  [{case_id}] XML 내보내기 버튼을 찾지 못했습니다.")
                    return False

                # 다운로드 이벤트 감지 후 버튼 클릭
                with self.page.expect_download(timeout=30000) as download_info:
                    export_btn.click()

                download = download_info.value
                download.save_as(save_path)

                logger.info(f"  [{case_id}] ✓ 다운로드 완료 → {save_path}")
                return True

            except PlaywrightTimeout:
                logger.warning(f"  [{case_id}] 시도 {attempt}/{config.RETRY_COUNT} 타임아웃")
            except Exception as e:
                logger.error(f"  [{case_id}] 시도 {attempt}/{config.RETRY_COUNT} 오류: {e}")

            if attempt < config.RETRY_COUNT:
                time.sleep(2)

        logger.error(f"  [{case_id}] ✗ {config.RETRY_COUNT}회 시도 모두 실패")
        return False

    # ----------------------------------------------------------
    #  전체 실행
    # ----------------------------------------------------------
    def run(self):
        start_time = datetime.now()
        logger.info("=" * 60)
        logger.info("  LSMV 자동 XML 다운로더 시작")
        logger.info(f"  시작 시각: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

        success_count = 0
        fail_count    = 0
        fail_list     = []

        try:
            self.start_browser()
            self.login()

            case_ids = self.get_all_case_ids()

            if not case_ids:
                logger.warning("다운로드할 케이스가 없습니다.")
                return

            logger.info(f"\n총 {len(case_ids)}개 케이스 다운로드를 시작합니다.\n")

            for i, case_id in enumerate(case_ids, 1):
                logger.info(f"[{i}/{len(case_ids)}] 케이스 처리 중: {case_id}")

                ok = self.download_case_xml(case_id)
                if ok:
                    success_count += 1
                else:
                    fail_count += 1
                    fail_list.append(case_id)

                # 서버 부하 방지 딜레이
                time.sleep(config.DELAY_BETWEEN_CASES)

        except KeyboardInterrupt:
            logger.info("\n사용자에 의해 중단되었습니다.")
        except Exception as e:
            logger.error(f"예기치 못한 오류 발생: {e}", exc_info=True)
        finally:
            self.stop_browser()

        # 결과 요약
        end_time = datetime.now()
        elapsed  = end_time - start_time
        logger.info("\n" + "=" * 60)
        logger.info("  다운로드 완료 요약")
        logger.info("=" * 60)
        logger.info(f"  성공: {success_count}개")
        logger.info(f"  실패: {fail_count}개")
        logger.info(f"  소요 시간: {elapsed}")
        if fail_list:
            logger.info(f"  실패한 케이스: {', '.join(fail_list)}")
        logger.info("=" * 60)


# ============================================================
#  실행 진입점
# ============================================================
if __name__ == "__main__":
    downloader = LsmvDownloader()
    downloader.run()
