#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import traceback as tb
import lxml.html as html

html.HtmlElement.__repr__ = html.tostring

class Empty(object):

    def __eq__(self, other):
        if isinstance(other, Empty):
            return True
        return False

    def __str__(self):
        return 'NULL'

class Extr(object):

    def match(self, content):
        if self._is_empty(content):
            return Empty()

        elif isinstance(content, (list, html.HtmlElement, basestring)):
            #print '==================='
            #print content
            #print '==================='
            try:
                ret = self.match_impl(content)
            except:
                print >> sys.stderr, 'Failed while extracting', content
                tb.print_exc()
                ret = Empty()
        else:
            #print content
            raise TypeError('unknown type')
        return ret

    #def match_impl(self, content):
    #    return content

    def extr_file(self, fname):
        with open(fname, 'r') as f:
            return self.extr_txt(f.read())

    def extr_txt(self, txt):
        return self.match(html.fromstring(txt))

    def _is_empty(self, content):
        return isinstance(content, Empty) \
                or content is None \
                or (hasattr(content, '__iter__') \
                    and (len(content) == 0 \
                        or all(c is None for c in content)))

    def __rshift__(self, other):
        return Seq(self, other)

    def __lshift__(self, other):
        return Foreach(self, other)

    def __or__(self, other):
        return Or(self, other)

    def __and__(self, other):
        return And(self, other)

class One(Extr):

    def __init__(self, expr, trans=None):
        self.expr = expr
        if trans is None:
            trans = lambda x: x
        self.trans = trans

    def match_impl(self, content):
        #print '==================='
        #print content
        m = content.xpath(self.expr)
        #print '--\n--'.join([ unicode(mi).encode('utf8') for mi in m ])
        if len(m) == 0:
            return Empty()
        elif len(m) > 1:
            #print m
            #print len(m)
            raise RuntimeError('more than one matched: ' + str(m))
        return self.trans(m[0])

class All(Extr):

    def __init__(self, expr, trans=None):
        self.expr = expr
        if trans is None:
            trans = lambda x: x
        self.trans = trans

    def match_impl(self, content):
        m = content.xpath(self.expr)
        if len(m) > 0:
            ret = [self.trans(mi) for mi in m]
            return ret
        else:
            return None

class And(Extr):

    def __init__(self, *extr_list):
        self.extr_list = []
        for extr in extr_list:
            if isinstance(extr, basestring):
                self.extr_list.append(One(extr))
            elif isinstance(extr, Extr):
                self.extr_list.append(extr)
            else:
                raise TypeError('Unknown extractor type: ' + str(extr.__class__))

    def match_impl(self, content):
        #print self.extr_list
        ret = [extr.match(content) for extr in self.extr_list]
        return ret

class Dict(Extr):

    def __init__(self, extr_dict, flat=True):
        self.extr_dict = {}
        for name, extr in extr_dict.iteritems():
            if isinstance(extr, basestring):
                self.extr_dict[name] = One(extr)
            elif isinstance(extr, Extr):
                self.extr_dict[name] = extr
            else:
                raise TypeError('Unknown extractor type: ' + str(extr.__class__))
        self.flat = flat

    def match_impl(self, content):
        #print '-------------------'
        #print content
        ret = {}
        for name, extr in self.extr_dict.iteritems():
            m = extr.match(content)
            if isinstance(m, dict) and self.flat:
                ret.update(m)
            else:
                ret[name] = m
        #print ret
        return ret

class NamedDict(Extr):

    def __init__(self, names):
        self.names = names

    def match_impl(self, content):
        ret = {}
        for i, n in enumerate(self.names):
            if n:
                ret[n] = content[i]
        return ret

class Seq(Extr):

    def __init__(self, *extrs):
        self.extrs = extrs

    def match_impl(self, content):
        ret = content
        for extr in self.extrs:
            ret = extr.match(ret)
            if self._is_empty(ret):
                ret = Empty()
                break
        return ret

class Or(Extr):

    def __init__(self, *extrs):
        self.extrs = extrs

    def match_impl(self, content):
        for extr in self.extrs:
            try:
                ret = extr.match(content)
            except:
                continue
            if not self._is_empty(ret):
                break
        return ret

class Foreach(Extr):

    def __init__(self, extr1, extr2):
        self.extr1 = extr1
        self.extr2 = extr2

    def match_impl(self, content):
        ret1 = self.extr1.match(content)
        if self._is_empty(ret1):
            return Empty()
        elif isinstance(ret1, list):
            ret2 = [self.extr2.match(c) for c in ret1]
        else:
            ret2 = extr.match(ret1)
        return ret2

#class Map(Extr):
#
#    def __init__(self, func):
#        self.func = func
#
#    def match_impl(self, content):
#        return self.func(content)

class Trans(Extr):

    def __init__(self, func):
        self.func = func

    def match_impl(self, content):
        return self.func(content)


def test1():
    html_doc = """
    <html><head><title>The Dormouse's story</title></head>
    <body>
    <p class="title"><b>The Dormouse's story</b></p>

    <p class="story">Once upon a time there were three little sisters; and their names were
    <a href="http://example.com/elsie" class="sister" id="link1">Elsie</a>,
    <a href="http://example.com/lacie" class="sister" id="link2">Lacie</a> and
    <a href="http://example.com/tillie" class="sister" id="link3">Tillie</a>;
    and they lived at the bottom of a well.</p>
    """

    #<p class="story">...</p>
    ht = html.fromstring(html_doc)
    mt = One('//body/p[@class="story"]') >> \
             Dict(dict(
                 a = 'a[@id="link1"]/text()',
                 b = One('a[@id="link2"]/text()') >> Trans(lambda x: x.upper()),
                 c = One('a[@id="not_exist"]/text()') | One('a[@id="link3"]/text()'),
                 text = All('.//text()') >> Trans(lambda x: ' '.join(x))
                 ))

    # it should output:
    # {'a': 'Elsie', 'text': 'Once upon a time there were three little sisters; and their names were\n     Elsie ,\n     Lacie  and\n     Tillie ;\n    and they lived at the bottom of a well.', 'c': 'Tillie', 'b': 'LACIE'}
    print mt.match(ht)

def main():
    test1()
    return

if __name__ == '__main__':
    main()
