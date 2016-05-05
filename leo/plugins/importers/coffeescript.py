#@+leo-ver=5-thin
#@+node:ekr.20160505094722.1: * @file importers/coffeescript.py
'''The @auto importer for coffeescript.'''
import re
import leo.core.leoGlobals as g
import leo.plugins.importers.basescanner as basescanner
#@+others
#@+node:ekr.20160505094722.2: ** class CoffeeScriptScanner
class CoffeeScriptScanner(basescanner.BaseScanner):
    
    #@+others
    #@+node:ekr.20160505101118.1: *3* coffee.__init__
    def __init__(self, importCommands, atAuto):
        '''Ctor for CoffeeScriptScanner class.'''
        basescanner.BaseScanner.__init__(self,
            importCommands,
            atAuto=atAuto, language='coffeescript')
        # self.c = importCommands.c
        # self.atAuto = atAuto
        self.def_name = None
        self.errors = 0
        self.tab_width = self.c.tab_width or -4
    #@+node:ekr.20160505104405.1: *3* coffee.adjust_lines (test)
    def adjust_lines(self, lines, indent=True):
        s = ''.join(lines)
        s = self.undentBody(s, ignoreComments=True)
        lines = g.splitLines(s)
        if indent:
            lines = [' '*4+z for z in lines]
        return lines
    #@+node:ekr.20160505114047.1: *3* coffee.class_name
    def class_name(self, s):
        '''Return the name of the class in line s.'''
        assert s.startswith('class')
        m = re.match(r'class(\s+)(\w+)',s)
        name = m.group(2) if m else '<**bad class name**>'
        return 'class ' + name
    #@+node:ekr.20160505102909.1: *3* coffee.skip_block
    def skip_block(self, lines):
        '''Return all lines of the block that starts at lines[0].'''
        trace = False and not g.unitTesting
        assert lines
        block_lines = [lines[0]]
        level1 = self.lws(lines[0])
        if trace: g.trace('first line', level1, repr(lines[0]))
        for i, s in enumerate(lines[1:]):
            strip = s.strip()
            level = self.lws(s)
            if trace: g.trace(level1, level, repr(s))
            if not strip or strip.startswith('#') or level > level1:
                block_lines.append(s)
            else:
                break
        if trace:
            print('')
            g.trace('block_lines...')
            for s in block_lines:
                print(s)
        return block_lines
    #@+node:ekr.20160505111722.1: *3* coffee.lws
    def lws(self, s):
        '''Return the indentation of line s.'''
        return g.computeLeadingWhitespaceWidth(s, self.tab_width)
    #@+node:ekr.20160505100917.1: *3* coffee.run
    def run(self, s, parent, parse_body=False, prepass=False):
        '''The top-level code for the coffeescript scanners.'''
        c = self.c
        changed = c.isChanged()
        if prepass:
            return False, []
        self.scan(s, parent, indent=False)
        ok = self.errors == 0
        # g.app.unitTestDict['result'] = ok
        if self.atAuto and ok:
            for p in parent.self_and_subtree():
                p.clearDirty()
            c.setChanged(changed)
        else:
            parent.setDirty(setDescendentsDirty=False)
            c.setChanged(True)
        return ok
    #@+node:ekr.20160505100917.2: *4* BaseScanner.escapeFalseSectionReferences
    def escapeFalseSectionReferences(self, s):
        '''
        Probably a bad idea.  Keep the apparent section references.
        The perfect-import write code no longer attempts to expand references
        when the perfectImportFlag is set.
        '''
        return s
        # result = []
        # for line in g.splitLines(s):
            # r1 = line.find('<<')
            # r2 = line.find('>>')
            # if r1>=0 and r2>=0 and r1<r2:
                # result.append("@verbatim\n")
                # result.append(line)
            # else:
                # result.append(line)
        # return ''.join(result)
    #@+node:ekr.20160505100917.3: *4* BaseScanner.checkBlanksAndTabs
    def checkBlanksAndTabs(self, s):
        '''Check for intermixed blank & tabs.'''
        # Do a quick check for mixed leading tabs/blanks.
        blanks = tabs = 0
        for line in g.splitLines(s):
            lws = line[0: g.skip_ws(line, 0)]
            blanks += lws.count(' ')
            tabs += lws.count('\t')
        ok = blanks == 0 or tabs == 0
        if not ok:
            self.report('intermixed blanks and tabs')
        return ok
    #@+node:ekr.20160505100917.4: *4* BaseScanner.regularizeWhitespace
    def regularizeWhitespace(self, s):
        '''Regularize leading whitespace in s:
        Convert tabs to blanks or vice versa depending on the @tabwidth in effect.
        This is only called for strict languages.'''
        changed = False; lines = g.splitLines(s); result = []; tab_width = self.tab_width
        if tab_width < 0: # Convert tabs to blanks.
            for line in lines:
                i, w = g.skip_leading_ws_with_indent(line, 0, tab_width)
                s = g.computeLeadingWhitespace(w, -abs(tab_width)) + line[i:] # Use negative width.
                if s != line: changed = True
                result.append(s)
        elif tab_width > 0: # Convert blanks to tabs.
            for line in lines:
                s = g.optimizeLeadingWhitespace(line, abs(tab_width)) # Use positive width.
                if s != line: changed = True
                result.append(s)
        if changed:
            action = 'tabs converted to blanks' if self.tab_width < 0 else 'blanks converted to tabs'
            message = 'inconsistent leading whitespace. %s' % action
            self.report(message)
        return ''.join(result)
    #@+node:ekr.20160505100958.1: *3* coffee.scan
    def scan(self, s1, parent, indent=True):
        '''Create an outline from Coffeescript (.coffee) file.'''
        if not s1.strip():
            return
        at_others, i, body_lines = False, 0, []
        lines = g.splitLines(s1)
        level = self.lws(lines[0])
        while i < len(lines):
            progress = i
            s = lines[i]
            strip = s.strip()
            is_class = g.match_word(s, 0, 'class')
            is_def = not is_class and self.starts_def(s)
            if strip.startswith('#'):
                body_lines.append(s)
                i += 1
            elif is_class or is_def:
                if not at_others:
                    at_others = True
                    body_lines.append('@others\n' if is_def else '    @others')
                block_lines = self.skip_block(lines[i:])
                assert block_lines
                i += len(block_lines)
                s2 = ''.join(block_lines[1:])
                child = parent.insertAsLastChild()
                child.h = self.class_name(s) if is_class else self.def_name
                child.b = strip + '\n' # Unindent the class/def line.
                self.scan(s2, child)
            else:
                body_lines.append(s)
                i += 1
            assert progress < i
        parent.b = parent.b + ''.join(self.adjust_lines(body_lines, indent=indent))
    #@+node:ekr.20160505113917.1: *3* coffee.starts_def
    def starts_def(self, s):
        '''
        Return True if line s starts a coffeescript function.
        Sets or clears the def_name ivar.
        '''
        m = re.match('(.*):(.*)->', s)
        self.def_name = m.group(1).strip() if m else None
        return bool(m)
    #@-others
#@-others
importer_dict = {
    'class': CoffeeScriptScanner,
    'extensions': ['.coffee', ],
}
#@-leo