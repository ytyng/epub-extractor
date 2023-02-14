#!/usr/bin/env python3

import os
import re
import shutil
import subprocess
import sys
import tempfile
import warnings
from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from functools import cached_property
from typing import Iterator, List, Callable, Optional, Dict
from xml.etree import ElementTree
from xml.etree.ElementTree import Element


def parse_xml_with_recover(xml_path: str) -> ElementTree:
    """
    xmlをパース
    & の使い方が悪いファイルがある場合、
    それをパースしようとするとエラーになるので、失敗したら文字列置換してリトライする。
    http://stackoverflow.com/questions/13046240/parseerror-not-well-formed
    -invalid-token-using-celementtree
    ここには、lxml の場合の対応方法があるが、python3 のxml ではやり方不明のため
    ( ElementTree.XMLParser のコンストラクタには recover 引数が無い)、
    自力で置換する
    """
    try:
        etree = ElementTree.parse(xml_path)
        return etree
    except ElementTree.ParseError as e:
        # ParseError の場合のみ、修復を試みる
        print('{}, {}'.format(e.__class__.__name__, e))

    xml_source = open(xml_path).read()
    # 修復!
    xml_source = xml_repair(xml_source)
    return ElementTree.fromstring(xml_source)


def convert_to_jpeg(
        source_file_path: str,
        destination_file_path: str,
        jpeg_quality=70
) -> None:
    """
    PNG を Jpeg に変換して移動
    """
    try:
        from PIL import Image
    except ImportError:
        print('PNG image found. Converting png to jpeg, require PIL.',
              file=sys.stderr)
        print('Try: "pip install PIL" or "pip install pillow"',
              file=sys.stderr)
        raise

    im = Image.open(source_file_path)
    im = im.convert("RGB")
    im.save(destination_file_path, 'jpeg', quality=jpeg_quality)
    os.remove(source_file_path)
    print('{} -> {}'.format(source_file_path, destination_file_path))


re_entity = re.compile(r'(>[^<]*)(&)([^<]*<)')
re_replace = re.compile(r'&(?!\w*?;)')


def xml_repair(xml_source: str) -> str:
    """
    XMLのソースコードの & を &amp; に変換する
    :param self:
    :param xml_source:
    :return:
    """

    def _replace(matcher):
        return re_replace.sub('&amp;', matcher.group(0))

    return re_entity.sub(_replace, xml_source)


def get_etree_namespace(element: Element) -> str:
    m = re.match('\{.*\}', element.tag)
    return m.group(0) if m else ''


def namespace_tag_query(element:Element) -> Callable[[str], str]:
    """
    element のネームスペースをバインドし、ネームスペースつきのタグ名を返す関数を返す
    """
    ns = get_etree_namespace(element)

    def _generate_query(tag_name):
        return './/{}{}'.format(ns, tag_name)

    return _generate_query


class ImageElementBase(metaclass=ABCMeta):
    class ItemHrefNotFound(Exception):
        pass

    @cached_property
    @abstractmethod
    def image_path(self) -> str:
        raise NotImplementedError

    @cached_property
    @abstractmethod
    def is_png(self) -> bool:
        """Is image type PNG"""
        raise NotImplementedError


class ImageElement(ImageElementBase):
    """
    item_element が、image/xxx の場合 (ページごとの XMLが無い場合)
    """
    def __init__(self, item_element: Element, itemref_element: Element,
                 epub_extractor: 'EpubExtractor'):
        self.item_element = item_element
        self.itemref_element = itemref_element
        self.epub_extractor = epub_extractor

    @cached_property
    def image_path(self) -> str:
        item_href = self.item_element.attrib.get('href', None)
        if not item_href:
            raise self.ItemHrefNotFound(f'{self.item_element}')
        return os.path.join(
            self.epub_extractor.content_base_dir, item_href)

    @cached_property
    def is_png(self) -> bool:
        return self.item_element.attrib.get('href', '').endswith('.png') or \
               self.item_element.attrib.get('media-type', '').endswith('/png')


class ImagePage(ImageElementBase):
    """
    画像ページ のクラス

    item_element が、xhtml で、その中に画像が含まれる場合の処理
    """

    class InvalidImageLength(Exception):
        pass

    class ImagePathAttrNotFound(Exception):
        pass

    def __init__(self, item_element: Element, itemref_element: Element,
                 epub_extractor: 'EpubExtractor'):
        self.item_element = item_element
        self.itemref_element = itemref_element
        self.epub_extractor = epub_extractor

    @cached_property
    def page_xhtml_path(self) -> str:
        """
        ページのXMLのパス
        例: item/xhtml/001.xhtml
        :return:
        """
        item_href = self.item_element.attrib.get('href', None)
        if not item_href:
            raise self.ItemHrefNotFound(self.item_element)

        return os.path.join(
            self.epub_extractor.content_base_dir, item_href)

    # page_xml_path = os.path.join(self.content_base_dir, item_href)

    @cached_property
    def page_xhtml_etree(self) -> ElementTree:
        # ページを解析
        return parse_xml_with_recover(self.page_xhtml_path)

    @cached_property
    def image_element(self) -> Element:

        if self.item_element.attrib.get('properties') == 'svg':
            # SVGラッピング 日本のコミックEPUBでよくある形式
            svg = self.page_xhtml_etree.find(
                './/{http://www.w3.org/2000/svg}svg')
            images = svg.findall('.//{http://www.w3.org/2000/svg}image')
            # 画像パスの属性は {http://www.w3.org/1999/xlink}href

        else:
            # ここ未テスト
            images = self.page_xhtml_etree.findall(
                './/{http://www.w3.org/1999/xhtml}img')
            # 画像パスの属性は src

        if len(images) >= 2:
            return self.get_largest_image_element(images)

        if len(images) != 1:
            raise self.InvalidImageLength('{}, {}'.format(
                self.item_element, len(images)))

        return images[0]

    @cached_property
    def image_path(self) -> str:
        """
        画像のフルパス
        :return:
        """
        return self.get_image_path_of_image_element(self.image_element)

    def get_largest_image_element(self, image_elements: List[Element]):
        """
        複数の image_element から一番サイズの大きな画像を取得
        """
        L = [(i, self.get_image_size_of_image_element(i))
             for i in image_elements]
        return list(sorted(L, key=lambda x: x[1], reverse=True))[0][0]

    # その他プロパティが必要であれば
    # self.image_element.attrib.get('width', None)
    # self.image_element.attrib.get('height', None)
    # self.image_element.attrib.get('width', None)
    def get_image_path_of_image_element(self, image_element: Element) -> str:
        attr_names = [
            '{http://www.w3.org/1999/xlink}href',
            'src',
            '{http://www.w3.org/1999/xlink}src',
        ]
        for attr_name in attr_names:
            val = image_element.attrib.get(attr_name)
            if val:
                return os.path.join(os.path.dirname(self.page_xhtml_path), val)
        raise self.ImagePathAttrNotFound(image_element.attrib)

    def get_image_size_of_image_element(self, image_element: Element) -> int:
        """
        画像のサイズを取得
        """
        return os.path.getsize(
            self.get_image_path_of_image_element(image_element))

    @cached_property
    def is_png(self) -> bool:
        return self.image_path.endswith('.png')

    @cached_property
    def item_href(self) -> Optional[str]:
        return self.item_element.attrib.get('href', None)


class EpubExtractorError(Exception):
    pass


class EpubExtractor:
    class EpubNotFound(EpubExtractorError):
        pass

    class NoEpubExtention(EpubExtractorError):
        pass

    class ContentXmlNotFound(EpubExtractorError):
        pass

    class IdRefNotFound(Exception):
        pass

    class ItemNotFound(Exception):
        pass

    class ItemHrefNotFound(Exception):
        pass

    class OutputDirectoryAlreadyExists(EpubExtractorError):
        pass

    def __init__(self, epub_file_path: str):
        if not os.path.exists(epub_file_path):
            raise self.EpubNotFound(epub_file_path)

        if not epub_file_path.endswith('.epub'):
            raise self.NoEpubExtention(epub_file_path)

        self.epub_file_path = epub_file_path
        self.setup()

    def setup(self) -> None:
        self.temp_dir = tempfile.mkdtemp(suffix='epub-dump-meta')
        # unzip
        subprocess.Popen(
            ('unzip', self.epub_file_path, "-d", self.temp_dir),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()

    def close(self) -> None:
        shutil.rmtree(self.temp_dir)

    @cached_property
    def content_xml_path(self) -> str:
        """
        content.xml (standard.opf) のファイルパスを返す
        """
        # META-INF/container.xml で固定
        container_xml_path = os.path.join(
            self.temp_dir, 'META-INF', 'container.xml')
        etree = parse_xml_with_recover(container_xml_path)
        # rootfile タグを探す
        rootfile_node = etree.find(
            ".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile")
        content_opf_path = rootfile_node.attrib['full-path']

        content_xml_path = os.path.join(
            self.temp_dir, content_opf_path)
        if not os.path.exists(content_xml_path):
            raise self.ContentXmlNotFound(content_xml_path)
        return content_xml_path

    @cached_property
    def content_xml_text(self) -> str:
        return open(self.content_xml_path).read()

    @cached_property
    def content_xml_etree(self) -> ElementTree:
        return parse_xml_with_recover(self.content_xml_path)

    @cached_property
    def content_base_dir(self) -> str:
        # ファイルのパス基準となるディレクトリ
        return os.path.dirname(self.content_xml_path)

    @cached_property
    def items_dict(self) -> Dict[str, Element]:
        """
        id をキーにした item の辞書
        """
        ntq = namespace_tag_query(self.content_xml_etree._root)
        manifest = self.content_xml_etree.find(ntq('manifest'))
        items = manifest.findall(ntq('item'))
        items_dict = {}  # type: Dict[str, Element]
        for item in items:
            id = item.attrib.get('id')
            items_dict[id] = item
        return items_dict

    @cached_property
    def itemrefs(self) -> Iterator[Element]:
        """
        spine > itemref をページ順に返すジェネレータ
        """
        ntq = namespace_tag_query(self.content_xml_etree._root)
        spine = self.content_xml_etree.find(ntq('spine'))
        itemrefs = spine.findall(ntq('itemref'))
        for itemref in itemrefs:
            yield itemref

    def _get_image_pages(self) -> Iterator[ImageElementBase]:
        items_dict = self.items_dict

        for itemref in self.itemrefs:  # type: Element

            idref = itemref.attrib.get('idref', None)
            if not idref:
                raise self.IdRefNotFound(itemref)

            if idref not in items_dict:
                raise self.ItemNotFound(idref)

            item = items_dict[idref]  # type: Element

            # item.attrib['media-type'] == 'image/jpeg' の場合
            media_type = item.attrib.get('media-type', '')
            if media_type.startswith('image/'):
                image_page = ImageElement(item, itemref, self)
            else:
                image_page = ImagePage(item, itemref, self)
            yield image_page

    @cached_property
    def image_pages(self) -> List[ImageElementBase]:
        return list(self._get_image_pages())

    def format_page_number(self, page_number: str) -> str:
        return '{:05d}'.format(page_number)

    def _move_jpeg_file(self, image_page: ImageElementBase, output_dir: str,
                        page_index: int, convert_png: bool = True,
                        copy: bool = True):
        source_image_path = image_page.image_path

        if image_page.is_png:
            if convert_png:
                # PNGを変換する場合
                destination_image_name = '{}.jpg'.format(
                    self.format_page_number(page_index))
                destination_image_path = os.path.join(
                    output_dir, destination_image_name)
                convert_to_jpeg(source_image_path, destination_image_path)
                return
            destination_image_name = '{}.png'.format(
                self.format_page_number(page_index))
        else:
            destination_image_name = '{}.jpg'.format(
                self.format_page_number(page_index))
        destination_image_path = os.path.join(
            output_dir, destination_image_name)
        if copy:
            shutil.copy(source_image_path, destination_image_path)
        else:
            shutil.move(source_image_path, destination_image_path)
        print('{} -> {}'.format(source_image_path, destination_image_name))

    def extract_images(
            self, output_dir: Optional[str] = None, convert_png: bool = True,
            delete_exists_dir: bool = False, copy: bool = True):
        """
        画像ファイルをディレクトリに展開(移動)
        """
        if not output_dir:
            output_dir, _ext = os.path.splitext(self.epub_file_path)
        if os.path.exists(output_dir):
            if delete_exists_dir:
                shutil.rmtree(output_dir)
            else:
                raise self.OutputDirectoryAlreadyExists(output_dir)

        os.mkdir(output_dir)

        for i, image_page in enumerate(self.image_pages, start=1):
            try:
                self._move_jpeg_file(
                    image_page, output_dir, i,
                    convert_png=convert_png,
                    copy=copy)
            except ImagePage.InvalidImageLength as e:
                warnings.warn('{} {}'.format(
                    e.__class__.__name__, e))

    @cached_property
    def metadata_element(self):
        """
        コンテンツXML ( standard.opf) 内の、metadata エレメント
        """
        ntq = namespace_tag_query(self.content_xml_etree._root)
        metadata = self.content_xml_etree.find(ntq('metadata'))
        return metadata

    @cached_property
    def last_page_number(self) -> int:
        return len(self.image_pages)

    def _get_item_href_from_image_page(self, image_page):
        """
        ページのリンク先を取得
        e.g.: 'xhtml/cover.xhtml'
        """
        path = getattr(image_page, 'item_href', None)
        if path:
            return path
        if hasattr(image_page, 'item_element') and \
                hasattr(image_page.item_element, 'attrib'):
            path = image_page.item_element.attrib.get('href', None)
            if path:
                return path
        # 未知のパターン。デバッグして調査してください。
        raise self.ItemHrefNotFound(image_page)

    @cached_property
    def xml_path_page_number_dict(self) -> Dict[str, Element]:
        """
        XMLファイルとページ番号の対応表
        :return: dict
        """
        return {
            self._get_item_href_from_image_page(image_page): i
            for i, image_page in enumerate(self.image_pages, start=1)
        }

    @cached_property
    def xml_path_page_number_dict_basename(self):
        """
        XMLファイルとページ番号の対応表 ファイル名のみ版
        :return: dict
        """
        return {
            os.path.basename(k): v for k, v
            in self.xml_path_page_number_dict.items()
        }

    def get_page_number_from_page_xml_path(self, page_xml_path, default=1):
        """
        ページXMLパスから画像番号を取得
        page_xml_path は XHTMLファイルのパスか、画像のパスになる(EPUB形式による)
        """
        if page_xml_path in self.xml_path_page_number_dict:
            return self.xml_path_page_number_dict[page_xml_path]
        else:
            return self.xml_path_page_number_dict_basename.get(
                os.path.basename(page_xml_path), default)

    @cached_property
    def navigation_xml(self):
        """
        :rtype: NavigationXml
        """
        return NavigationXml(self)

    @cached_property
    def toc_ncx(self):
        """
        :rtype: TocNcx
        """
        return TocNcx(self)

    @cached_property
    def meta(self):
        """
        :rtype: EpubMeta
        """
        return EpubMeta(self)

    def get_toc_table(self):
        """
        目次情報を取得
        """
        try:
            if self.toc_ncx.cleaned_toc_ncx_data:
                # toc.ncx がパースできたらそれを使う
                return self.toc_ncx.cleaned_toc_ncx_data
        except TocNcx.TocNcxNotFound:
            pass
        try:
            if self.navigation_xml.cleaned_navigation_xml_data:
                # toc.ncx がパースできなければ、navigation-xml から取得を試す
                return self.navigation_xml.cleaned_navigation_xml_data
        except NavigationXml.NavigationXmlNotFound:
            pass
        return None

    @staticmethod
    def print_json(object):
        import json
        print(json.dumps(object, ensure_ascii=False, indent=2))

    def dump_meta(self):
        pass
        # self.toc_xml_path
        # self.navigation_xml.debug_cleaned_navigation_xml_data()

        # self.toc_ncx.debug_cleaned_toc_ncx_data()


class EpubMeta:
    def __init__(self, epub_extractor):
        self.ee = epub_extractor
        self.meta_element = self.ee.metadata_element

    def _get_text_dc(self, tag_name):
        tag = self.meta_element.find(
            './/{}{}'.format(
                "{http://purl.org/dc/elements/1.1/}", tag_name
            ))
        if tag is not None:
            return tag.text
        else:
            return None

    def _get_texts_dc(self, tag_name):
        return [e.text for e in self.meta_element.findall(
            './/{}{}'.format(
                "{http://purl.org/dc/elements/1.1/}", tag_name
            ))]

    @cached_property
    def title(self):
        return self._get_text_dc('title')

    @cached_property
    def publisher(self):
        return self._get_text_dc('publisher')

    @cached_property
    def identifier(self):
        return self._get_text_dc('identifier')

    @cached_property
    def language(self):
        return self._get_text_dc('language')

    @cached_property
    def creators(self):
        return self._get_texts_dc('creator')

    def as_ordered_dict(self):
        return OrderedDict([
            ('title', self.title),
            ('publisher', self.publisher),
            ('identifier', self.identifier),
            ('language', self.language),
            ('creators', self.creators),
            ('meta', self.meta_dict),
        ])

    def meta_tags(self):
        return self.meta_element.findall(
            './/{http://www.idpf.org/2007/opf}meta')

    @cached_property
    def meta_dict(self):
        od = OrderedDict()
        for mt in self.meta_tags():
            if mt.attrib.get('refines'):
                # refines 今回は無視
                continue
            if mt.attrib.get('name') and mt.attrib.get('content'):
                od[mt.attrib.get('name')] = mt.attrib.get('content')
                continue
            if mt.attrib.get('property'):
                od[mt.attrib.get('property')] = mt.text
                continue
        return od


class NavigationXml:
    """
    NAVIGATION XML (Required BeautifulSoup4)
    """

    class NavigationXmlNotFound(EpubExtractorError):
        pass

    def __init__(self, epub_extractor):
        self.ee = epub_extractor

    @cached_property
    def navigation_xml_path(self):
        ntq = namespace_tag_query(self.ee.content_xml_etree._root)
        manifest = self.ee.content_xml_etree.find(ntq('manifest'))
        items = manifest.findall(ntq('item'))
        for item in items:
            if item.attrib.get('id') == 'toc' \
                    or item.attrib.get('properties') == 'nav':
                return os.path.join(
                    self.ee.content_base_dir,
                    item.attrib.get('href'))
        raise self.NavigationXmlNotFound()

    @cached_property
    def navigation_xml_etree(self):
        return parse_xml_with_recover(self.navigation_xml_path)

    @cached_property
    def navigation_xml_bs4(self):
        from bs4 import BeautifulSoup
        return BeautifulSoup(open(self.navigation_xml_path), "html.parser")

    @cached_property
    def navigation_xml_data(self):
        def _gen():
            bs = self.navigation_xml_bs4
            for a in bs.find_all('a'):
                href = a['href']
                page_number = self.ee.get_page_number_from_page_xml_path(href)
                yield OrderedDict([
                    ('page_xml', href),
                    ('start_page', page_number),
                    ('section_title', a.text),
                ])

        return list(_gen())

    @cached_property
    def cleaned_navigation_xml_data(self):
        attended = set()
        navs = []
        for o in sorted(self.navigation_xml_data,
                        key=lambda x: x['start_page']):
            if o['start_page'] in attended:
                continue
            attended.add(o['start_page'])
            if navs:
                navs[-1]['end_page'] = o['start_page'] - 1
            navs.append(o)
        if navs:
            navs[-1]['end_page'] = self.ee.last_page_number
        return navs

    def debug_cleaned_navigation_xml_data(self):
        for o in self.cleaned_navigation_xml_data:
            print('{}-{} {}'.format(
                self.ee.format_page_number(o['start_page']),
                self.ee.format_page_number(o['end_page']),
                o['section_title']
            ))


class TocNcx:
    """
    TOC NCX
    """

    class TocNcxNotFound(EpubExtractorError):
        pass

    def __init__(self, epub_extractor):
        self.ee = epub_extractor

    @cached_property
    def toc_ncx_etree(self) -> ElementTree:
        return parse_xml_with_recover(self.toc_ncx_path)

    @cached_property
    def toc_ncx_path(self) -> str:
        manifest = self.ee.content_xml_etree.find(
            './/{http://www.idpf.org/2007/opf}manifest')
        items = manifest.findall('.//{http://www.idpf.org/2007/opf}item')
        for item in items:
            if item.attrib.get('media-type') == 'application/x-dtbncx+xml' \
                    or item.attrib.get('id') == 'ncx':
                return os.path.join(
                    self.ee.content_base_dir,
                    item.attrib.get('href'))
        raise self.TocNcxNotFound()

    @cached_property
    def toc_ncx_data(self) -> List[OrderedDict]:
        """
        toc.ncx を解析した辞書
        """

        def _gen():
            ntq = namespace_tag_query(self.toc_ncx_etree._root)
            for np in self.toc_ncx_etree.findall(ntq('navPoint')):
                text = np.find(ntq('text'))
                content = np.find(ntq('content'))
                src = content.attrib.get('src')
                page_number = self.ee.get_page_number_from_page_xml_path(src)
                # play_order = np.attrib.get('playOrder')
                yield OrderedDict([
                    ('page_xml', src),
                    ('start_page', page_number),
                    ('section_title', text.text),
                ])

        return list(_gen())

    @cached_property
    def cleaned_toc_ncx_data(self):
        attended = set()
        navs = []
        for o in sorted(self.toc_ncx_data,
                        key=lambda x: x['start_page']):
            if o['start_page'] in attended:
                continue
            attended.add(o['start_page'])
            if navs:
                navs[-1]['end_page'] = o['start_page'] - 1
            navs.append(o)
        if navs:
            navs[-1]['end_page'] = self.ee.last_page_number
        return navs

    def debug_cleaned_toc_ncx_data(self) -> None:
        for o in self.cleaned_toc_ncx_data:
            print('{}-{} {}'.format(
                self.ee.format_page_number(o['start_page']),
                self.ee.format_page_number(o['end_page']),
                o['section_title']
            ))
