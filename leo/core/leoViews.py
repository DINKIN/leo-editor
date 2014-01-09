# -*- coding: utf-8 -*-
#@+leo-ver=5-thin
#@+node:ekr.20131230090121.16504: * @file leoViews.py
#@@first

'''Support for @views trees and related operations.'''

#@@language python
#@@tabwidth -4
#@+<< imports >>
#@+node:ekr.20131230090121.16506: ** << imports >> (leoViews.py)
import leo.core.leoGlobals as g
#@-<< imports >>
#@+others
#@+node:ekr.20140106215321.16672: ** class OrganizerData
class OrganizerData:
    '''A class containing all data for a particular organizer node.'''
    def __init__ (self,h,unl,unls):
        self.childIndex = 0
            # The ultimate childIndex this organizer node.
        self.closed = False
            # True if this organizer node no longer accepts new nodes.
        self.h = h
            # The headline of this organizer node).
        self.moved = False
            # True: the organizer node has already been moved.
        self.n_unorganized_nodes = 0
            # The number of unorganized nodes preceding this node (for childIndex).
        self.organized_nodes = []
            # The list of positions organized by this organizer node.
        self.organizer_children = []
            # The organizer nodes that will become children of this organizer node.
        self.organizer_parent = None
            # The organizer node (if any) that will become the parent of this organizer node.
            # It *is* valid for this to be None!
        self.number_of_children = 0
            # The number of children that have been "virtually" moved to this node.
        self.p = None
            # The position of this organizer node.
        self.parent = None
            # The original parent node of all nodes organized by this organizer node.
            # If organizer_parent is None, this will be the parent of the organizer node.
        self.source_unl = None
            # The unl of self.parent.
        self.unl = unl
            # The unl of the organizer node itself.
        self.unls = unls
            # The unls contained in this organizer node.
        self.visited = False
            # True: demote_helper has already handled this organizer node.
    def __repr__(self):
        return 'OrganizerData: %s' % (self.h or '<no headline>')
    __str__ = __repr__
#@+node:ekr.20131230090121.16508: ** class ViewController
class ViewController:
    #@+<< docstring >>
    #@+node:ekr.20131230090121.16507: *3*  << docstring >> (class ViewController)
    '''
    A class to handle @views trees and related operations.
    Such trees have the following structure:

    - @views
      - @auto-view <unl of @auto node>
        - @organizers
          - @organizer <headline>
        - @clones
        
    The body text of @organizer and @clones consists of unl's, one per line.
    '''
    #@-<< docstring >>
    #@+others
    #@+node:ekr.20131230090121.16509: *3*  vc.ctor & vc.init
    def __init__ (self,c):
        '''Ctor for ViewController class.'''
        self.c = c
        self.init()
        
    def init(self):
        self.global_bare_organizer_node_list = []
        self.global_moved_node_list = []
        self.organizer_data_list = []
        self.organizer_unls = []
        ### self.root_data = None
        self.temp_node = None
        self.views_node = None
    #@+node:ekr.20131230090121.16514: *3* vc.Entry points
    #@+node:ekr.20140102052259.16394: *4* vc.pack & helper
    def pack(self):
        '''
        Undoably convert c.p to a packed @view node, replacing all cloned
        children of c.p by unl lines in c.p.b.
        '''
        c,u = self.c,self.c.undoer
        self.init()
        changed = False
        root = c.p
        # Create an undo group to handle changes to root and @views nodes.
        # Important: creating the @views node does *not* invalidate any positions.'''
        u.beforeChangeGroup(root,'view-pack')
        if not self.has_views_node():
            changed = True
            bunch = u.beforeInsertNode(c.rootPosition())
            views = self.find_views_node()
                # Creates the @views node as the *last* top-level node
                # so that no positions become invalid as a result.
            u.afterInsertNode(views,'create-views-node',bunch)
        # Prepend @view if need.
        if not root.h.strip().startswith('@'):
            changed = True
            bunch = u.beforeChangeNodeContents(root)
            root.h = '@view ' + root.h.strip()
            u.afterChangeNodeContents(root,'view-pack-update-headline',bunch)
        # Create an @view node as a clone of the @views node.
        bunch = u.beforeInsertNode(c.rootPosition())
        new_clone = self.create_view_node(root)
        if new_clone:
            changed = True
            u.afterInsertNode(new_clone,'create-view-node',bunch)
        # Create a list of clones that have a representative node
        # outside of the root's tree.
        reps = [self.find_representative_node(root,p)
            for p in root.children()
                if self.is_cloned_outside_parent_tree(p)]
        reps = [z for z in reps if z is not None]
        if reps:
            changed = True
            bunch = u.beforeChangeTree(root)
            c.setChanged(True)
            # Prepend a unl: line for each cloned child.
            unls = ['unl: %s\n' % (self.unl(p)) for p in reps]
            root.b = ''.join(unls) + root.b
            # Delete all child clones in the reps list.
            v_reps = set([p.v for p in reps])
            while True:
                for child in root.children():
                    if child.v in v_reps:
                        child.doDelete()
                        break
                else: break
            u.afterChangeTree(root,'view-pack-tree',bunch)
        if changed:
            u.afterChangeGroup(root,'view-pack')
            c.selectPosition(root)
            c.redraw()
    #@+node:ekr.20140102052259.16397: *5* vc.create_view_node
    def create_view_node(self,root):
        '''
        Create a clone of root as a child of the @views node.
        Return the *newly* cloned node, or None if it already exists.
        '''
        c = self.c
        # Create a cloned child of the @views node if it doesn't exist.
        views = self.find_views_node()
        for p in views.children():
            if p.v == c.p.v:
                return None
        p = root.clone()
        p.moveToLastChildOf(views)
        return p
    #@+node:ekr.20140102052259.16395: *4* vc.unpack
    def unpack(self):
        '''
        Undoably unpack nodes corresponding to leading unl lines in c.p to child clones.
        Return True if the outline has, in fact, been changed.
        '''
        c,root,u = self.c,self.c.p,self.c.undoer
        self.init()
        # Find the leading unl: lines.
        i,lines,tag = 0,g.splitLines(root.b),'unl:'
        for s in lines:
            if s.startswith(tag): i += 1
            else: break
        changed = i > 0
        if changed:
            bunch = u.beforeChangeTree(root)
            # Restore the body
            root.b = ''.join(lines[i:])
            # Create clones for each unique unl.
            unls = list(set([s[len(tag):].strip() for s in lines[:i]]))
            for unl in unls:
                p = self.find_absolute_unl_node(unl)
                if p: p.clone().moveToLastChildOf(root)
                else: g.trace('not found: %s' % (unl))
            c.setChanged(True)
            c.undoer.afterChangeTree(root,'view-unpack',bunch)
            c.redraw()
        return changed
    #@+node:ekr.20131230090121.16511: *4* vc.update_before_write_at_auto_file
    def update_before_write_at_auto_file(self,root):
        '''
        Update the @organizer and @clones nodes in the @auto-view node for
        root, an @auto node. Create the @organizer or @clones nodes as needed.
        '''
        c = self.c
        self.init()
        clone_data,organizers_data = [],[]
        for p in root.subtree():
            if p.isCloned():
                rep = self.find_representative_node(root,p)
                if rep:
                    unl = self.relative_unl(p,root)
                    gnx = rep.v.gnx
                    clone_data.append((gnx,unl),)
            if self.is_organizer_node(p,root):
                organizers_data.append(p.copy())
        if clone_data:
            at_clones = self.find_clones_node(root)
            at_clones.b = ''.join(['gnx: %s\nunl: %s\n' % (z[0],z[1])
                for z in clone_data])
        if organizers_data:
            organizers = self.find_organizers_node(root)
            organizers.deleteAllChildren()
            for p in organizers_data:
                organizer = organizers.insertAsLastChild()
                organizer.h = '@organizer: %s' % p.h
                # The organizer node's unl is implicit in each child's unl.
                organizer.b = '\n'.join(['unl: ' + self.relative_unl(child,root)
                    for child in p.children()])
                        ### if not self.is_organizer_node(child,root)]) ###
        if clone_data or organizers_data:
            c.redraw()
    #@+node:ekr.20131230090121.16513: *4* vc.update_after_read_at_auto_file & helpers
    def update_after_read_at_auto_file(self,p):
        '''
        Recreate all organizer nodes and clones for a single @auto node
        using the corresponding @organizer: and @clones nodes.
        '''
        assert self.is_at_auto_node(p),p
        organizers = self.has_organizers_node(p)
        self.init()
        if organizers:
            self.create_organizer_nodes(organizers,p)
        clones = self.has_clones_node(p)
        if clones:
            self.create_clone_links(clones,p)
        # g.trace('clones',clones and clones.h)
        # g.trace('organizers',organizers and organizers.h)
    #@+node:ekr.20131230090121.16545: *5* vc.create_clone_link
    def create_clone_link(self,gnx,root,unl):
        '''
        Replace the node in the @auto tree with the given unl by a
        clone of the node outside the @auto tree with the given gnx.
        '''
        trace = False and not g.unitTesting
        p1 = self.find_relative_unl_node(root,unl)
        p2 = self.find_gnx_node(gnx)
        if p1 and p2:
            if trace: g.trace('relink',gnx,p2.h,'->',p1.h)
            if p1.b == p2.b:
                p2._relinkAsCloneOf(p1)
                return True
            else:
                g.es('body text mismatch in relinked node',p1.h)
                return False
        else:
            if trace: g.trace('relink failed',gnx,root.h,unl)
            return False
    #@+node:ekr.20131230090121.16533: *5* vc.create_clone_links
    def create_clone_links(self,clones,root):
        '''
        Recreate clone links from an @clones node.
        @clones nodes contain pairs of lines (gnx,unl)
        '''
        lines = g.splitLines(clones.b)
        gnxs = [s[4:].strip() for s in lines if s.startswith('gnx:')]
        unls = [s[4:].strip() for s in lines if s.startswith('unl:')]
        # g.trace('clones.b',clones.b)
        if len(gnxs) == len(unls):
            ok = True
            for gnx,unl in zip(gnxs,unls):
                ok = ok and self.create_clone_link(gnx,root,unl)
            return ok
        else:
            g.trace('bad @clones contents',gnxs,unls)
            return False
    #@+node:ekr.20131230090121.16532: *5* vc.create_organizer_nodes & helpers
    def create_organizer_nodes(self,at_organizers,root):
        '''
        root is an @auto node. Create an organizer node in root's tree for each
        child @organizer: node of the given @organizers node.
        '''
        c = self.c
        # Create the OrganizerData objects and corresponding ivars of this class.
        self.create_organizer_data(at_organizers,root)
        # Create the organizer nodes in a temporary location so positions remain valid.
        self.create_actual_organizer_nodes()
        # Demote organized nodes to be children of the organizer nodes.
        self.demote_organized_nodes(root)
        # Move nodes to their final locations.
        self.move_nodes()
        # Move comments in organized nodes to organizer nodes.
        self.move_comments(root)
        c.selectPosition(root)
        c.redraw()
    #@+node:ekr.20140106215321.16674: *6* vc.create_organizer_data (ensures d.parent)
    def create_organizer_data(self,at_organizers,root):
        '''
        Create OrganizerData nodes for all @organizer: nodes
        in the given @organizers node.
        '''
        trace = False and not g.unitTesting
        tag = '@organizer:'
        # Important: we must completely reinit all data here.
        self.organizer_data_list = []
        ### self.root_data = OrganizerData('**root_data**',unl='',unls=[])
        ### self.root_data.p = root.copy()
        for at_organizer in at_organizers.children():
            h = at_organizer.h
            if h.startswith(tag):
                unls = self.get_at_organizer_unls(at_organizer)
                if unls:
                    organizer_unl = self.drop_unl_tail(unls[0])
                    h = h[len(tag):].strip()
                    data = OrganizerData(h,organizer_unl,unls)
                    self.organizer_data_list.append(data)
                    self.organizer_unls.append(organizer_unl)
                else:
                    g.trace('no unls:',at_organizer.h)
        # Now that self.organizer_unls is complete, compute the source unls.
        for data in self.organizer_data_list:
            data.source_unl = self.source_unl(self.organizer_unls,data.unl)
            data.parent = self.find_relative_unl_node(root,data.source_unl)
            if not data.parent:
                g.trace('***no data.parent: use root','unl:',repr(data.unl),
                    'source_unl:',repr(data.source_unl),'\nunls:',data.unls)
                data.parent = root
            if trace: g.trace(
                'unl:',data.unl,
                'source:',data.source_unl,
                'parent:',data.parent and data.parent.h)
    #@+node:ekr.20140106215321.16675: *6* vc.create_actual_organizer_nodes
    def create_actual_organizer_nodes(self):
        '''
        Create all organizer nodes as children of a temp node that leaves all
        positions unchanged.
        '''
        c = self.c
        last = c.lastTopLevel()
        temp = self.temp_node = last.insertAfter()
        temp.h = 'ViewController.temp_node'
        for data in self.organizer_data_list:
            data.p = temp.insertAsLastChild()
            data.p.h = data.h
    #@+node:ekr.20140106215321.16677: *6* vc.demote_organized_nodes & helpers
    def demote_organized_nodes(self,root):
        '''Demote organized nodes to be children of organizer nodes.'''
        for data in self.organizer_data_list:
            if not data.visited:
                self.demote_helper(data,root)
                    # Sets data.visited for all relevant OrganzierData instances.
    #@+node:ekr.20140104112957.16587: *7* vc.demote_helper & helpers
    def demote_helper(self,data,root):
        '''
        Demote nodes for all OrganizerData instances having the same source as
        the given instance.
        '''
        trace = False # and not g.unitTesting
        if trace: g.trace('=====',root and root.h or '*no root*',
            data and data.parent and data.parent.h or '*no data.parent*')
        # Find and mark as visited all OrganizerData instances having the same source as data.
        data_list = self.find_all_organizer_nodes(data)
        # Compute the list of positions of nodes organized by each OrganizerData instance.
        for d in data_list:
            self.compute_organized_positions(d,root)
        # Compute the parent/child relationships for all organizer nodes.
        self.compute_tree_structure(data_list,root)
        # The main line: move children of data.parent to organizer nodes.
        active = None # The organizer node that is presently accumulating nodes.
        demote_pending = [] # Lists of pending demotions.
        def add(active,child):
            if trace: g.trace('active',active,
                'active.p',active.p and active.p.h,
                'child',child and child.h)
            self.global_moved_node_list.append((active.p,child.copy()),)
        def pending(active,child):
            if trace: g.trace('active',active,
                'active.p',active.p and active.p.h,
                'child',child and child.h)
            demote_pending.append((active.p,child.copy()),)
        n = 0 # The number of *unorganized* preceding nodes.
        for child in data.parent.children():
            # Find the organizer (if any) that organizes child.
            found = None
            for d in data_list:
                for p in d.organized_nodes:
                    if p == child:
                        found = d ; break
                if found: break
            if trace: g.trace('-----',child.h,'found:',found and found.h,
                'active',active and active.h)
            if found is None:
                if active:
                    pending(active,child)
                else:
                    # Pending nodes will *not* be organized.
                    n += 1 + len(demote_pending) # Add 1 for the child.
                    demote_pending = []
            elif found == active:
                # Pending nodes *will* be organized.
                if trace:
                    for z,d in demote_pending: g.trace('extra',z.h)
                for data in demote_pending:
                    active,child = data
                    add(active,child)
                demote_pending = []
                add(active,child)
            else: # found != active.
                # Pending nodes will *not* be organized.
                n += len(demote_pending)
                demote_pending = []
                active,n = self.switch_active_organizer(active,child,data,data_list,found,n)
                if active:
                    # switch_active_organizer bumps n only for bare organizer nodes.
                    add(active,child)
        if active:
            active.closed = True
        ### Demote all result nodes in reverse order so positions remain stable.
        ### for p,data in reversed(demote):
        ###    assert data.p
        ###    p.moveToFirstChildOf(data.p)
    #@+node:ekr.20140108081031.16611: *8* vc.compute_organized_positions
    def compute_organized_positions(self,data,root):
        '''Compute all the positions by the given OrganizerData instance.'''
        trace = False and not g.unitTesting
        raw_unls = [self.drop_all_organizers_in_unl(self.organizer_unls,unl)
            for unl in data.unls]
        for raw_unl in list(set(raw_unls)):
            p = self.find_relative_unl_node(root,raw_unl)
            if p: data.organized_nodes.append(p.copy())
            elif trace: g.trace('not found',raw_unl)
        if trace:
            g.trace('data',data.h,'\nraw_unls',raw_unls,
                '\norganized_nodes',[z.h for z in data.organized_nodes])
    #@+node:ekr.20140108081031.16612: *8* vc.compute_tree_structure
    def compute_tree_structure(self,data_list,root):
        '''
        Set the organizer_parent and organizer_children ivars for each entry in
        data_list.
        '''
        trace = True # and not g.unitTesting
        organizer_unls = [d.unl for d in data_list]
        for d in data_list:
            for unl in d.unls:
                if unl in organizer_unls:
                    i = organizer_unls.index(unl)
                    d2 = data_list[i]
                    if trace: g.trace('found organizer unl:',d.h,'==>',d2.h)
                    d.organizer_children.append(d2)
                    d2.organizer_parent = d
        # If there is no organizer parent, the organizer node will be
        # the child of an *ordinary* node, namely d.parent.
        for d in data_list:
            assert d.parent,d.h
                # create_organizer_data now ensures d.parent is set.
    #@+node:ekr.20140108081031.16610: *8* vc.find_all_organizer_nodes
    def find_all_organizer_nodes(self,data):
        '''
        Return the list of all OrganizerData instances organizing the same
        imported source node as data and set each visited bit.
        '''
        # Compute the list.
        aList = [z for z in self.organizer_data_list
            if z.source_unl == data.source_unl]
        # Check that all parents match.
        assert all([z.parent == data.parent for z in aList]),[
            z for z in aList if z.parent != data.parent]
        # Check that all visited bits are clear.
        assert all([not z.visited for z in aList]),[
            z for z in aList if z.visited]
        # Set all visited bits.
        for z in aList:
            z.visited = True
        return aList
    #@+node:ekr.20140106215321.16685: *8* vc.switch_active_organizer (test)
    def switch_active_organizer(self,active,child,data,data_list,found,n):
        '''Terminate the active organizer and start the found organizer.
        Return found, unless it has already been terminated.
        Set the found.childIndex.
        '''
        trace = False # and not g.unitTesting
        if active:
            active.closed = True
        assert found
        if found.closed:
            g.trace('Already exited',found.h)
            return None,n
        active = found
        if active.moved:
            g.trace('****already moved***',active.h)
            return active,n
        else:
            active.moved = True
            assert active.p,active.h
            if active.organizer_parent:
                # The organizer node is a child of *another* organizer node.
                # Just add it to the global moved list(!)
                parent = active.organizer_parent.p
                self.global_moved_node_list.append((parent,active.p),)
                return active,n
            else:
                # The organizer node is a child of an *ordinary* node.
                parent = active.parent
                g.trace('move bare',active.p and active.p.h,'to child',n,'of',
                    parent and parent.h or '***no parent***') 
            return active,n+1
    #@+node:ekr.20140106215321.16678: *6* vc.move_nodes (test)
    def move_nodes(self):
        '''Move nodes to their final location and delete the temp node.'''
        c = self.c
        # Move nodes into organizers, in reversed order to preserve positions.
        for parent,p in reversed(self.global_moved_node_list):
            g.trace(parent.h,p.h)
            ### p.moveToLastChildOf(parent.p)
        # Move all bare organizers.
        # A: For each parent, sort nodes on n.
        g.trace('===== moving bare nodes =====')
        d = {} # Keys are vnodes, values are lists of tuples (n,parent,p)
        for parent,p,n in self.global_bare_organizer_node_list:
            key = parent.v
            aList = d.get(key,[])
            if (n,parent,p) not in aList:
                aList.append((n,parent,p),)
                d[key] = aList
        # B: For each parent, add nodes in childIndex order.
        def key_func(obj):
            return obj[0]
        for key in d.keys():
            aList = d.get(key)
            alist.sort(key=key_func)
            for data in aList:
                n,parent,p = data
                g.trace(n,parent,p)
                ### p.moveToNthChildOf(parent.p,n)
        # Delete the temp_node.
        ### self.temp_node.doDelete()
    #@+node:ekr.20140106215321.16679: *6* vc.move_comments & helper
    def move_comments(self,root):
        '''Move comments from organizer nodes to organizer nodes.'''
        c = self.c
        if 0: ### Not ready yet.
            to_be_deleted = []
            for data in self.organizer_data_list:
                p2 = self.migrate_organizer_node_comments(data.p,root)
                if p2: to_be_deleted.append(p2)
            g.trace('to_be_deleted',[p.h for p in to_be_deleted])
            c.deletePositionsInList(to_be_deleted)
    #@+node:ekr.20140105055318.16753: *7* v.migrate_organizer_node_comments
    def migrate_organizer_node_comments(self,p,root):
        '''
        p is an organizer node. Let back be p.back(). If back contains nothing
        but comments, move back.b to p.b and return back, indicating that back
        is to deleted later.
        '''
        back = p.back()
        if back and not back.hasChildren() and self.is_comment_node(back,root):
            if back.b: p.b = p.b + back.b
            return back
        else:
            return None
    #@+node:ekr.20131230090121.16515: *3* vc.Helpers
    #@+node:ekr.20140103105930.16448: *4* vc.at_auto_view_body and match_at_auto_body
    def at_auto_view_body(self,p):
        '''Return the body text for the @auto-view node for p.'''
        # Note: the unl of p relative to p is simply p.h,
        # so it is pointless to add that to @auto-view node.
        return 'gnx: %s\n' % p.v.gnx
        
    def match_at_auto_body(self,p,auto_view):
        '''Return True if any line of auto_view.b matches the expected gnx line.'''
        return p.b == 'gnx: %s\n' % auto_view.v.gnx
    #@+node:ekr.20131230090121.16522: *4* vc.clean_nodes (not used)
    def clean_nodes(self):
        '''Delete @auto-view nodes with no corresponding @auto nodes.'''
        c = self.c
        views = self.has_views_node()
        if not views:
            return
        # Remember the gnx of all @auto nodes.
        d = {}
        for p in c.all_unique_positions():
            if self.is_at_auto_node(p):
                d[p.v.gnx] = True
        # Remember all unused @auto-view nodes.
        delete = []
        for child in views.children():
            s = child.b and g.splitlines(child.b)
            gnx = s[len('gnx'):].strip()
            if gnx not in d:
                g.trace(child.h,gnx)
                delete.append(child.copy())
        for p in reversed(delete):
            p.doDelete()
        c.selectPosition(views)
    #@+node:ekr.20131230090121.16526: *4* vc.comment_delims
    def comment_delims(self,p):
        '''Return the comment delimiter in effect at p, an @auto node.'''
        c = self.c
        d = g.get_directives_dict(p)
        s = d.get('language') or c.target_language
        language,single,start,end = g.set_language(s,0)
        return single,start,end
    #@+node:ekr.20140103062103.16442: *4* vc.find...
    # The find node command create the node if not found.
    #@+node:ekr.20140102052259.16402: *5* vc.find_absolute_unl_node
    def find_absolute_unl_node(self,unl):
        '''Return a node matching the given absolute unl.'''
        aList = unl.split('-->')
        if aList:
            first,rest = aList[0],'-->'.join(aList[1:])
            for parent in self.c.rootPosition().self_and_siblings():
                if parent.h.strip() == first.strip():
                    if rest:
                        return self.find_relative_unl_node(parent,rest)
                    else:
                        return parent
        return None
    #@+node:ekr.20131230090121.16520: *5* vc.find_at_auto_view_node & helper
    def find_at_auto_view_node (self,root):
        '''
        Return the @auto-view node for root, an @auto node.
        Create the node if it does not exist.
        '''
        views = self.find_views_node()
        p = self.has_at_auto_view_node(root)
        if not p:
            p = views.insertAsLastChild()
            p.h = '@auto-view:' + root.h[len('@auto'):].strip()
            p.b = self.at_auto_view_body(root)
        return p
    #@+node:ekr.20131230090121.16516: *5* vc.find_clones_node
    def find_clones_node(self,root):
        '''
        Find the @clones node for root, an @auto node.
        Create the @clones node if it does not exist.
        '''
        c = self.c
        h = '@clones'
        auto_view = self.find_at_auto_view_node(root)
        clones = g.findNodeInTree(c,auto_view,h)
        if not clones:
            clones = auto_view.insertAsLastChild()
            clones.h = h
        return clones
    #@+node:ekr.20131230090121.16547: *5* vc.find_gnx_node
    def find_gnx_node(self,gnx):
        '''Return the first position having the given gnx.'''
        # This is part of the read logic, so newly-imported
        # nodes will never have the given gnx.
        for p in self.c.all_unique_positions():
            if p.v.gnx == gnx:
                return p
        return None
    #@+node:ekr.20131230090121.16518: *5* vc.find_organizers_node
    def find_organizers_node(self,root):
        '''
        Find the @organizers node for root, and @auto node.
        Create the @organizers node if it doesn't exist.
        '''
        c = self.c
        h = '@organizers'
        auto_view = self.find_at_auto_view_node(root)
        assert auto_view
        organizers = g.findNodeInTree(c,auto_view,h)
        if not organizers:
            organizers = auto_view.insertAsLastChild()
            organizers.h = h
        return organizers
    #@+node:ekr.20131230090121.16539: *5* vc.find_relative_unl_node
    def find_relative_unl_node(self,parent,unl):
        '''
        Return the node in parent's subtree matching the given unl.
        The unl is relative to the parent position.
        '''
        trace = False # and not g.unitTesting
        p = parent
        if not unl:
            if trace: g.trace('empty unl. return parent:',parent)
            return parent
        for s in unl.split('-->'):
            for child in p.children():
                if child.h == s:
                    p = child
                    break
            else:
                if trace: g.trace('failure','parent',parent.h,'unl:',unl)
                return None
        if trace: g.trace('success',p)
        return p
    #@+node:ekr.20131230090121.16544: *5* vc.find_representative_node
    def find_representative_node (self,root,target):
        '''
        root is an @auto node. target is a clones node within root's tree.
        Return a node *outside* of root's tree that is cloned to target,
        preferring nodes outside any @<file> tree.
        Never return any node in any @views or @view tree.
        '''
        trace = False and not g.unitTesting
        assert target
        assert root
        # Pass 1: accept only nodes outside any @file tree.
        p = self.c.rootPosition()
        while p:
            if p.h.startswith('@view'):
                p.moveToNodeAfterTree()
            elif p.isAnyAtFileNode():
                p.moveToNodeAfterTree()
            elif p.v == target.v:
                if trace: g.trace('success 1:',p,p.parent())
                return p
            else:
                p.moveToThreadNext()
        # Pass 2: accept any node outside the root tree.
        p = self.c.rootPosition()
        while p:
            if p.h.startswith('@view'):
                p.moveToNodeAfterTree()
            elif p == root:
                p.moveToNodeAfterTree()
            elif p.v == target.v:
                if trace: g.trace('success 2:',p,p.parent())
                return p
            else:
                p.moveToThreadNext()
        g.trace('no representative node for:',target,'parent:',target.parent())
        return None
    #@+node:ekr.20131230090121.16519: *5* vc.find_views_node
    def find_views_node(self):
        '''
        Find the first @views node in the outline.
        If it does not exist, create it as the *last* top-level node,
        so that no existing positions become invalid.
        '''
        c = self.c
        p = g.findNodeAnywhere(c,'@views')
        if not p:
            last = c.rootPosition()
            while last.hasNext():
                last.moveToNext()
            p = last.insertAfter()
            p.h = '@views'
            # c.selectPosition(p)
            # c.redraw()
        return p
    #@+node:ekr.20140103062103.16443: *4* vc.has...
    # The has_xxx commands return None if the node does not exist.
    #@+node:ekr.20140103105930.16447: *5* vc.has_at_auto_view_node
    def has_at_auto_view_node(self,root):
        '''
        Return the @auto-view node corresponding to root, an @root node.
        Return None if no such node exists.
        '''
        c = self.c
        assert self.is_at_auto_node(root)
        views = g.findNodeAnywhere(c,'@views')
        if views:
            # Find a direct child of views with matching headline and body.
            for p in views.children():
                if self.match_at_auto_body(p,root):
                    return p
        return None
    #@+node:ekr.20131230090121.16529: *5* vc.has_clones_node
    def has_clones_node(self,root):
        '''
        Find the @clones node for an @auto node with the given unl.
        Return None if it does not exist.
        '''
        auto_view = self.has_at_auto_view_node(root)
        return g.findNodeInTree(self.c,auto_view,'@clones') if auto_view else None
    #@+node:ekr.20131230090121.16531: *5* vc.has_organizers_node
    def has_organizers_node(self,root):
        '''
        Find the @organizers node for root, an @auto node.
        Return None if it does not exist.
        '''
        auto_view = self.has_at_auto_view_node(root)
        return g.findNodeInTree(self.c,auto_view,'@organizers') if auto_view else None
    #@+node:ekr.20131230090121.16535: *5* vc.has_views_node
    def has_views_node(self):
        '''Return the @views or None if it does not exist.'''
        return g.findNodeAnywhere(self.c,'@views')
    #@+node:ekr.20140105055318.16755: *4* v.is...
    #@+node:ekr.20131230090121.16524: *5* vc.is_at_auto_node
    def is_at_auto_node(self,p):
        '''Return True if p is an @auto node.'''
        return g.match_word(p.h,0,'@auto') and not g.match(p.h,0,'@auto-')
            # Does not match @auto-rst, etc.
    #@+node:ekr.20140102052259.16398: *5* vc.is_cloned_outside_parent_tree
    def is_cloned_outside_parent_tree(self,p):
        '''Return True if a clone of p exists outside the tree of p.parent().'''
        return len(list(set(p.v.parents))) > 1
    #@+node:ekr.20140105055318.16754: *5* vc.is_comment_node
    def is_comment_node(self,p,root):
        '''Return True if p.b contains nothing but comments or blank lines.'''
        single,start,end = self.comment_delims(root)
        assert single or start and end,'bad delims: %r %r %r' % (single,start,end)
        if single:
            for s in g.splitLines(p.b):
                s = s.strip()
                if s and not s.startswith(single) and not g.isDirective(s):
                    return False
            else:
                return True
        else:
            def check_comment(s):
                done,in_comment = False,True
                i = s.find(end)
                if i > -1:
                    tail = s[i+len(end):].strip()
                    if tail: done = True
                    else: in_comment = False
                return done,in_comment
            
            done,in_comment = False,False
            for s in g.splitLines(p.b):
                s = s.strip()
                if not s:
                    pass
                elif in_comment:
                    done,in_comment = check_comment(s)
                elif g.isDirective(s):
                    pass
                elif s.startswith(start):
                    done,in_comment = check_comment(s[len(start):])
                else:
                    # g.trace('fail 1: %r %r %r...\n%s' % (single,start,end,s)
                    return False
                if done:
                    return False
            # All lines pass.
            return True
    #@+node:ekr.20131230090121.16525: *5* vc.is_organizer_node
    def is_organizer_node(self,p,root):
        '''
        Return True if p is an organizer node in the given @auto tree.
        '''
        return p.hasChildren() and self.is_comment_node(p,root)
    #@+node:ekr.20140105055318.16760: *4* v.unls...
    #@+node:ekr.20140105055318.16762: *5* vc.drop_all_organizers_in_unl
    def drop_all_organizers_in_unl(self,organizer_unls,unl):
        '''Drop all organizer unl's in unl, recreating the imported url.'''
        def key(s):
            return s.count('-->')
        for s in reversed(sorted(organizer_unls,key=key)):
            if unl.startswith(s):
                s2 = self.drop_unl_tail(s)
                unl = s2 + unl[len(s):]
        return unl
    #@+node:ekr.20140105055318.16761: *5* vc.drop_unl_tail & vc.drop_unl_parent
    def drop_unl_tail(self,unl):
        '''Drop the last part of the unl.'''
        return '-->'.join(unl.split('-->')[:-1])

    def drop_unl_parent(self,unl):
        '''Drop the penultimate part of the unl.'''
        aList = unl.split('-->')
        return '-->'.join(aList[:-2] + aList[-1:])
    #@+node:ekr.20140106215321.16673: *5* vc.get_at_organizer_unls
    def get_at_organizer_unls(self,p):
        '''Return the unl: lines in an @organizer: node.'''
        return [s[len('unl:'):].strip()
            for s in g.splitLines(p.b)
                if s.startswith('unl:')]

    #@+node:ekr.20131230090121.16541: *5* vc.relative_unl & unl
    def relative_unl(self,p,root):
        '''Return the unl of p relative to the root position.'''
        result = []
        for p in p.self_and_parents():
            if p == root:
                break
            else:
                result.append(p.h)
        return '-->'.join(reversed(result))

    def unl(self,p):
        '''Return the unl corresponding to the given position.'''
        return '-->'.join(reversed([p.h for p in p.self_and_parents()]))
    #@+node:ekr.20140106215321.16680: *5* vc.source_unl
    def source_unl(self,organizer_unls,organizer_unl):
        '''Return the unl of the source node for the given organizer_unl.'''
        return self.drop_all_organizers_in_unl(organizer_unls,organizer_unl)
    #@-others
#@+node:ekr.20140102051335.16506: ** vc.Commands
@g.command('view-pack')
def view_pack_command(event):
    c = event.get('c')
    if c and c.viewController:
        c.viewController.pack()

@g.command('view-unpack')
def view_unpack_command(event):
    c = event.get('c')
    if c and c.viewController:
        c.viewController.unpack()
#@-others
#@-leo