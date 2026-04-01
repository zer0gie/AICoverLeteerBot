import re
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup


@dataclass
class VacancyData:
    url: str
    title: str
    company: str
    description: str


class VacancyParser:
    def __init__(self, timeout: int = 20) -> None:
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; VacancyCoverBot/1.0)",
            },
            follow_redirects=True,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def parse(self, url: str) -> VacancyData:
        response = await self._client.get(url)
        response.raise_for_status()
        html = response.text

        soup = BeautifulSoup(html, "html.parser")
        title = self._extract_title(soup)
        company = self._extract_company(soup)
        description = self._extract_description(soup)

        return VacancyData(
            url=url,
            title=title or "Не удалось определить должность",
            company=company or "Не удалось определить компанию",
            description=description[:6000],
        )

    def _extract_title(self, soup: BeautifulSoup) -> str:
        selectors = [
            "h1[data-qa='vacancy-title']",
            "h1",
            "meta[property='og:title']",
        ]
        for selector in selectors:
            element = soup.select_one(selector)
            if not element:
                continue
            if element.name == "meta":
                content = element.attrs.get("content", "").strip()
                if content:
                    return content
            text = element.get_text(" ", strip=True)
            if text:
                return text
        return ""

    def _extract_company(self, soup: BeautifulSoup) -> str:
        selectors = [
            "[data-qa='vacancy-company-name']",
            "[data-qa='bloko-header-2']",
        ]
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(" ", strip=True)
                if text:
                    return text
        return ""

    def _extract_description(self, soup: BeautifulSoup) -> str:
        selectors = [
            "[data-qa='vacancy-description']",
            ".vacancy-description",
            "main",
            "body",
        ]
        for selector in selectors:
            element = soup.select_one(selector)
            if not element:
                continue
            text = element.get_text("\n", strip=True)
            text = re.sub(r"\n{3,}", "\n\n", text)
            if len(text) > 300:
                return text
        return "Описание вакансии не найдено."
