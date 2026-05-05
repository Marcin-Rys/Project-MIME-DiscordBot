import discord
from discord import app_commands
import json
import os
from typing import Optional
# import aiosqlite - for now not using it

class LangUtils(app_commands.Translator):
    def __init__(self, lang_dir: str):
        self.translations = {}
        self._load_all_languages(lang_dir)
        
    def _load_all_languages(self, lang_dir: str):
        print(f"#lang_utils.py | Loading translations from folder: {lang_dir} ---")
        if not os.path.isdir(lang_dir):
            print(f"#lang_utils.py | ERROR! | Directory '{lang_dir}' doesn't exists!")
            return

        for lang_code in os.listdir(lang_dir):
            lang_path = os.path.join(lang_dir, lang_code)
            if os.path.isdir(lang_path):
                self.translations[lang_code] = {}
                for filename in os.listdir(lang_path):
                    if filename.endswith(".json"):
                        module_name = filename[:-5].lower()
                        file_path = os.path.join(lang_path, filename)
                        with open(file_path, 'r', encoding="utf-8") as f:
                            try:
                                self.translations[lang_code][module_name] = json.load(f)
                            except json.JSONDecodeError:
                                print(f"lang_uils.py | ERROR! | Translation file is damaged: {file_path} ---")
        print(f"#lang_utils.py | OK | Loaded translation for modules: {list(self.translations.keys())} ---")

    async def translate(self, string: app_commands.locale_str, locale: discord.Locale, context: app_commands.TranslationContext) -> Optional[str]:
        #loading key from extras
        key = string.extras.get("key")
        if not key:
            #no translation without key
            return None
        
        lang_code = str(locale).split('-')[0]

        try:
            module_name, string_key = key.split(":", 1)
            module_name = module_name.lower()
        except ValueError:
            print("#lang_utils | Warning! | Wrong key value")
            return None
            
        #searching for translatioin using key from "extras"
        translation = self.translations.get(lang_code, {}).get(module_name, {}).get(string_key)
        if translation is not None:
            return translation
        
        #fallback to en language
        return self.translations.get("en", {}).get(module_name, {}).get(string_key)
    
    def get_translation(self, key: str, locale=None, fallback: str = "Błąd", **kwargs) -> str:
        
        lang_code = str(locale).split('-')[0] if locale else "en"
        try:
            module_name, string_key = key.split(":", 1)
            module_name = module_name.lower()
        except (ValueError, AttributeError):
            return fallback.format(**kwargs) if kwargs else fallback

        translation = self.translations.get(lang_code, {}).get(module_name, {}).get(string_key)
        if translation is not None:
            return translation.format(**kwargs) if kwargs else translation

        fallback_translation = self.translations.get("en", {}).get(module_name, {}).get(string_key)
        if fallback_translation is not None:
            return fallback_translation.format(**kwargs) if kwargs else fallback_translation
        
        return fallback.format(**kwargs) if kwargs else fallback