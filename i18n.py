"""
i18n - Internationalization support using gettext

This module provides translation functionality for the Dayflow application.
Default language: Simplified Chinese (zh_CN)

Per-module translation files are located at:
    locales/{lang}/LC_MESSAGES/{module_path}.mo

Example:
    core/analysis.py -> locales/ko_KR/LC_MESSAGES/core/analysis.mo
"""
from pathlib import Path
from typing import List, Optional, Dict

from babel.support import Translations, NullTranslations
from babel.messages.pofile import read_po
from babel.messages.mofile import write_mo

import config

# Global state
_current_language = config.DEFAULT_LANGUAGE  # Track current language
_locales_dir = Path(__file__).parent / "locales"


class MultiDomainTranslator:
    """
    A translator that can load and use multiple translation domains.

    This allows each Python module to have its own .mo file while using
    a single global _() function.
    
    Uses Babel for translation support when available.
    """

    def __init__(self, language: str, locales_dir: Path):
        self.language = language
        self.locales_dir = locales_dir
        self._cache: Dict[str, NullTranslations] = {}
        self._load_all_translations()
        
    def _load_all_translations(self):
        """
        Pre-load all available .mo files for the current language.

        This ensures the translator has access to all translation domains.
        """
        # Find all .mo files for the current language
        lang_dir = _locales_dir / self.language / 'LC_MESSAGES'

        if not lang_dir.exists():
            return

        # Recursively find all .mo files
        for mo_file in lang_dir.rglob('*.mo'):
            # Convert file path to domain name
            # e.g., locales/ko_KR/LC_MESSAGES/core/analysis.mo -> core/analysis
            rel_path = mo_file.relative_to(lang_dir)
            domain = str(rel_path.with_suffix('')).replace('\\', '/')

            # Load the translation for this domain
            self.get_translation(domain)

    def get_translation(self, domain: str):
        """Get translation for a specific domain (module path)."""
        if domain not in self._cache:
            try:
                trans = Translations.load(
                    dirname=str(self.locales_dir),
                    locales=[self.language],
                    domain=domain
                )
                self._cache[domain] = trans
            except Exception:
                self._cache[domain] = NullTranslations()

        return self._cache[domain]

    def gettext(self, message: str) -> str:
        """
        Translate a message by trying all loaded domains.

        Since we can't know which module the string comes from at runtime
        without inspecting the call stack, we try all loaded domains.
        The first non-identity translation wins.
        """
        # If Chinese, no translation needed
        if self.language == 'zh_CN':
            return message

        # Try all cached translations
        for domain, trans in self._cache.items():
            translated = trans.gettext(message)
            if translated != message:
                return translated

        # No translation found, return original
        return message


# Global translator instance
_translator: Optional[MultiDomainTranslator] = None


def _(message: str) -> str:
    """
    Global translation function.

    Usage:
        from i18n import _

        text = _("中文文本")
    """
    global _translator

    if _translator is None or _current_language == 'zh_CN':
        return message

    return _translator.gettext(message)

def load_translations(language: str) -> Optional[MultiDomainTranslator]:
    """
    Load translations for the specified language.

    Args:
        language: Language code (e.g., 'ko_KR', 'en', 'zh_CN')
        
    Returns:
        MultiDomainTranslator instance or None if no translation needed
    """

    # Default to simplified Chinese
    if language is None:
        language = config.DEFAULT_LANGUAGE

    # Default to simplified Chinese (no translation needed since source is in Chinese)
    if language == config.DEFAULT_LANGUAGE:
        return None

    # Create multi-domain translator
    return MultiDomainTranslator(language, _locales_dir)

def init_i18n(language: Optional[str] = None, storage=None) -> None:
    """
    Initialize the i18n system with the specified language.

    Args:
        language: Language code (e.g., 'ko_KR', 'en', 'zh_CN').
                 If None and storage is provided, will read from storage.get_setting('language')
                 Otherwise defaults to simplified Chinese
        storage: Storage instance to read language preference from
    """
    global _translator, _current_language

    # Get language from storage if not specified
    if language is None and storage is not None:
        try:
            language = storage.get_setting('language', config.DEFAULT_LANGUAGE)
        except Exception:
            language = config.DEFAULT_LANGUAGE

    _translator = load_translations(language)
    _current_language = language


def get_current_language() -> str:
    """Get the current language code."""
    return _current_language


def get_supported_languages() -> List[str]:
    ret = []
    ret.append(config.DEFAULT_LANGUAGE)
    for lang_dir in _locales_dir.iterdir():
        lang = lang_dir.name
        if (lang_dir.is_dir() and lang not in ret):
            ret.append(lang)

    return list(ret)

def compile_po(po_file: Path):
    """
    Compile .po files to .mo files in the specified directory.

    Args:
        path: Path to the directory containing .po files
    """
    
    po_file_rel = po_file.relative_to(_locales_dir)
    mo_file = po_file.with_suffix('.mo')
    
    
    # po_file: {lang}/LC_MESSAGES/...
    locale = po_file_rel.parts[0]
    
    with open(po_file, 'rb') as fs:
        catalog = read_po(fs, locale)
    
    with open(mo_file, 'wb') as fs:
        write_mo(fs, catalog)

def build_po():
    for po_file in _locales_dir.rglob('*.po'):
        print(f"Compiling... {po_file}")
        compile_po(po_file)

if __name__ == "__main__":
    build_po()
