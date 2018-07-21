# -*- coding: utf-8 -*-
"""
Author: Juliette Monsel
License: GNU GPLv3
Source: This repository

Table made out of a Treeview with possibility to drag rows and columns and to sort columns.
"""
# TODO: issues when dragging row and using mousewheel
# TODO: check whether everything looks fine in windows
# TODO: scroll horizontally when swapping columns like for rows?

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    import Tkinter as tk
    import ttk
from PIL import ImageTk, Image
from ttkwidgets.utilities import get_assets_directory, os


IM_DRAG = os.path.join(get_assets_directory(), "drag.png")


class Table(ttk.Treeview):
    """
    Table widget displays a table with options to drag rows and columns and
    to sort columns.

    This widget is based on the ttk.Treeview and shares many options and methods
    with it.
    """
    _init = False
    _initialized = False  # to kwnow whether class bindings and Table layout have been created yet

    def __init__(self, master=None, show='headings', drag_cols=True, drag_rows=True,
                 sortable=True, class_='Table', **kwargs):
        """
        Construct a Table with parent master.

        KEYWORDS OPTIONS

            master: parent window
            drag_cols: boolean to set whether columns are draggable
            drag_rows: boolean to set whether rows are draggable
            sortable: boolean to set whether columns are sortable by clicking on
                      their headings (the type of data (str, float ...) can be
                      set with the column method)
            show: which parts of the treeview to show (same as the Treeview option)
            **kwargs: all ttk.Treeview options

        """
        ttk.Treeview.__init__(self, master, show=show, **kwargs)
        # copy of the Treeview to show the dragged column
        self._visual_drag = ttk.Treeview(self, show=show, **kwargs)

        # specific options
        self._drag_rows = bool(drag_rows)
        self._drag_cols = bool(drag_cols)
        self._im_draggable = Image.open(IM_DRAG)
        self._im_not_draggable = Image.new('RGBA', self._im_draggable.size)
        if self._drag_cols:
            self._im_drag = ImageTk.PhotoImage(self._im_draggable, master=self)
        else:
            self._im_drag = ImageTk.PhotoImage(self._im_not_draggable, master=self)
        self._sortable = bool(sortable)
        if self._sortable:
            for col in self['columns']:
                self.heading(col, command=lambda c=col: self._sort_column(c, True))
        self._column_types = {col: str for col in self['columns']}

        # style and class bindings initialization
        if not Table._initialized:
            self._initialize_style()
            for seq in self.bind_class('Treeview'):
                self.bind_class('Table', seq, self.bind_class('Treeview', seq))
                print(seq)
            Table._initialized = True

        if not self['style']:
            self['style'] = 'Table'

        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Motion>", self._on_motion)

        # distance between cursor and column left border
        # (needed to drag around self._visual_drag)
        self._dx = 0
        self._dy = 0
        self._dragged_row = None  # row being dragged
        self._dragged_col = None  # column being dragged
        self._dragged_col_width = 0
        self._dragged_row_height = 0
        self._dragged_col_x = 0  # x coordinate of the dragged column upper left corner
        self._dragged_row_y = 0  # y coordinate of the dragged column upper left corner
        self._dragged_col_neighbor_widths = (None, None)
        self._dragged_row_neighbor_heights = (None, None)
        self._dragged_col_index = None

        self.config = self.configure

    def _initialize_style(self):
        style = ttk.Style(self)
        style.layout('Table', style.layout('Treeview'))
        style.layout('Table.Heading',
                     [('Treeheading.cell', {'sticky': 'nswe'}),
                      ('Treeheading.border',
                       {'sticky': 'nswe',
                        'children': [('Treeheading.padding',
                                      {'sticky': 'nswe',
                                       'children': [('Treeheading.image', {'side': 'left', 'sticky': ''}),
                                                    ('Treeheading.text', {'sticky': 'we'})]})]})])
        config = style.configure('Treeview')
        if config:
            style.configure('Table', **config)
        config_heading = style.configure('Treeview.Heading')
        if config_heading:
            style.configure('Table.Heading', **config_heading)
        style_map = style.map('Treeview')
        # add noticeable disabled style
        fieldbackground = style_map.get('fieldbackground', [])
        fieldbackground.append(("disabled", '#E6E6E6'))
        style_map['fieldbackground'] = fieldbackground
        foreground = style_map.get('foreground', [])
        foreground.append(("disabled", 'gray40'))
        style_map['foreground'] = foreground
        background = style_map.get('background', [])
        background.append(("disabled", '#E6E6E6'))
        style_map['background'] = background
        style.map('Table', **style_map)

        style_map_heading = style.map('Treeview.Heading')
        background = style_map_heading.get('background', [])
        style.map('Table.Heading', **style_map_heading)

    def __setitem__(self, key, value):
        self.configure(**{key: value})

    def __getitem__(self, key):
        return self.cget(key)

    def _swap_columns(self, side):
        """Swap dragged column with its side (=left/right) neighbor."""
        displayed_cols = list(self["displaycolumns"])
        if displayed_cols[0] == "#all":
            displayed_cols = list(self["columns"])
        i1 = self._dragged_col_index
        i2 = i1 + 1 if side == 'right' else i1 - 1
        if 0 <= i2 < len(displayed_cols):
            displayed_cols[i1] = displayed_cols[i2]
            displayed_cols[i2] = self._dragged_col
            self["displaycolumns"] = displayed_cols
            if side == 'left':
                right = self._dragged_col_neighbor_widths[0]
                self._dragged_col_x -= right
                if i2 > 0:
                    left = ttk.Treeview.column(self, displayed_cols[i2 - 1], 'width')
                else:
                    left = None
            else:
                left = self._dragged_col_neighbor_widths[1]
                self._dragged_col_x += left
                if i2 < len(displayed_cols) - 1:
                    right = ttk.Treeview.column(self, displayed_cols[i2 + 1], 'width')
                else:
                    right = None
            self._dragged_col_index = i2
            self._dragged_col_neighbor_widths = (left, right)

    def _swap_rows(self, side):
        """Swap dragged row with its side (=above/below) neighbor."""
        if side == 'above':
            prev_it = self.prev(self._dragged_row)
            if prev_it:
                self.move(self._dragged_row, '', self.index(prev_it))
        else:
            next_it = self.next(self._dragged_row)
            if next_it:
                self.move(self._dragged_row, '', self.index(next_it))
        self.see(self._dragged_row)
        bbox = self.bbox(self._dragged_row)
        if bbox:
            self._dragged_row_y = bbox[1]
            self._dragged_row_height = bbox[3]
        self._visual_drag.see(self._dragged_row)

    def _on_press(self, event):
        """Start dragging column on left click."""
        if 'disabled' not in self.state():
            region = self.identify_region(event.x, event.y)
            # --- column dragging
            if self._drag_cols and region == 'heading':
                col = self.identify_column(event.x)
                self._dragged_col = ttk.Treeview.column(self, col, 'id')
                # get column width
                self._dragged_col_width = w = ttk.Treeview.column(self, col, 'width')
                # get x coordinate of the upper left corner of the column
                x = event.x
                while self.identify_region(x, event.y) == 'heading':
                    x -= 1
                x_sep = x
                w_sep = 0
                while self.identify_region(x_sep, event.y) == 'separator':
                    w_sep += 1
                    x_sep -= 1
                if event.x - x <= self._im_drag.width():  # start dragging
                    x = x - w_sep // 2 - 1
                    self._dragged_col_x = x
                    # neighboring columns
                    displayed_cols = list(self["displaycolumns"])
                    if displayed_cols[0] == "#all":
                        displayed_cols = list(self["columns"])
                    self._dragged_col_index = i1 = displayed_cols.index(self._dragged_col)
                    if i1 > 0:
                        left = ttk.Treeview.column(self, displayed_cols[i1 - 1], 'width')
                    else:
                        left = None
                    if i1 < len(displayed_cols) - 1:
                        right = ttk.Treeview.column(self, displayed_cols[i1 + 1], 'width')
                    else:
                        right = None
                    self._dragged_col_neighbor_widths = (left, right)
                    # distance between cursor and column left border
                    self._dx = x - event.x
                    self._visual_drag.column(self._dragged_col, width=w)
                    self._visual_drag.configure(displaycolumns=[self._dragged_col])
                    if 'headings' in tuple(str(p) for p in self['show']):
                        self._visual_drag.configure(show='headings')
                    else:
                        self._visual_drag.configure(show='')
                    self._visual_drag.place(in_=self, x=x, y=0, anchor='nw',
                                            width=w + 2, relheight=1)
                    self._visual_drag.state(('active', ))
                    self._visual_drag.update_idletasks()
                    self._visual_drag.yview_moveto(self.yview()[0])
                else:
                    self._dragged_col = None
            # --- row dragging
            elif self._drag_rows and region == 'cell':
                self._dragged_row = self.identify_row(event.y)
                self._visual_drag.configure(displaycolumns=self['displaycolumns'],
                                            height=1)
                for col in self['columns']:
                    self._visual_drag.column(col, width=self.column(col, 'width'))
                if 'tree' in tuple(str(p) for p in self['show']):
                    self._visual_drag.configure(show='tree')
                else:
                    self._visual_drag.configure(show='')
                bbox = self.bbox(self._dragged_row)
                self._dy = bbox[1] - event.y
                self._dragged_row_y = bbox[1]
                self._dragged_row_height = bbox[3]
                prev_it = self.prev(self._dragged_row)
                if prev_it != '':
                    bbox_prev = self.bbox(prev_it)
                    if not bbox_prev:
                        above = None
                    else:
                        above = self.bbox(prev_it)[3]
                else:
                    above = None
                next_it = self.next(self._dragged_row)
                if next_it != '':
                    bbox_next = self.bbox(next_it)
                    if not bbox_next:
                        below = None
                    else:
                        below = bbox_next[3]
                else:
                    below = None
                self._dragged_row_neighbor_heights = (above, below)
                self._visual_drag.place(in_=self, x=0, y=bbox[1],
                                        height=self._visual_drag.winfo_reqheight() + 2,
                                        anchor='nw', relwidth=1)
                self._visual_drag.selection_add(self._dragged_row)
                self.selection_remove(self._dragged_row)
                self._visual_drag.update_idletasks()
                self._visual_drag.see(self._dragged_row)

    def _on_release(self, event):
        """Stop dragging."""
        if self._drag_cols or self._drag_rows:
            self._visual_drag.place_forget()
            self._dragged_col = None
            self._dragged_row = None

    def _on_motion(self, event):
        """Drag around label if visible."""
        if self._visual_drag.winfo_ismapped():
            # --- column dragging
            if self._drag_cols and self._dragged_col is not None:
                x = self._dx + event.x
                self._visual_drag.place_configure(x=x)
                # if one border of the dragged column is beyon the middle of the
                # neighboring column, swap them
                if (self._dragged_col_neighbor_widths[0] is not None and x < self._dragged_col_x - self._dragged_col_neighbor_widths[0] / 2):
                    self._swap_columns('left')
                elif (self._dragged_col_neighbor_widths[1] is not None and x > self._dragged_col_x + self._dragged_col_neighbor_widths[1] / 2):
                    self._swap_columns('right')
            # --- row dragging
            elif self._drag_rows and self._dragged_row is not None:
                y = self._dy + event.y
                self._visual_drag.place_configure(y=y)
                if (self._dragged_row_neighbor_heights[0] is not None and y < self._dragged_row_y - self._dragged_row_neighbor_heights[0] / 2):
                    self._swap_rows('above')
                elif (self._dragged_row_neighbor_heights[1] is not None and y > self._dragged_row_y + self._dragged_row_neighbor_heights[1] / 2):
                    self._swap_rows('below')
                self.selection_remove(self._dragged_row)

    def _sort_column(self, column, reverse):
        """Sort column."""
        if 'disabled' not in self.state():
            l = [(self.set(k, column), k) for k in self.get_children('')]
            l.sort(reverse=reverse, key=lambda x: self._column_types[column](x[0]))
            for index, (val, k) in enumerate(l):
                self.move(k, "", index)
            self.heading(column, command=lambda: self._sort_column(column, not reverse))

    def cget(self, key):
        if key == 'sortable':
            return self._sortable
        elif key == 'drag_cols':
            return self._drag_cols
        elif key == 'drag_rows':
            return self._drag_rows
        else:
            return ttk.Treeview.cget(self, key)

    def column(self, column, option=None, **kw):
        """
        Query or modify the options for the specified column.

        If kw is not given, returns a dict of the column option values. If
        option is specified then the value for that option is returned.
        Otherwise, sets the options to the corresponding values.

        options: 'type' (content type for sorting, default=str), all Treeview column options
        """
        config = False
        if option == 'type':
            return self._column_types[column]
        elif 'type' in kw:
            config = True
            self._column_types[column] = kw.pop('type')
        if kw:
            self._visual_drag.column(ttk.Treeview.column(self, column, 'id'), option, **kw)
        if kw or option:
            return ttk.Treeview.column(self, column, option, **kw)
        elif not config:
            res = ttk.Treeview.column(self, column, option, **kw)
            res['type'] = self._column_types[column]
            return res

    def configure(self, cnf=None, **kw):
        if cnf == 'drag_cols':
            return ('drag_cols', self._drag_cols)
        elif cnf == 'drag_rows':
            return ('drag_rows', self._drag_rows)
        elif cnf == 'sortable':
            return ('sortable', self._sortable)
        else:
            config = False
            if 'sortable' in kw:
                config = True
                self._sortable = bool(kw.pop('sortable'))
                if self._sortable:
                    for col in self['columns']:
                        ttk.Treeview.heading(self, col,
                                             command=lambda c=col: self._sort_column(c, True))
                else:
                    for col in self['columns']:
                        ttk.Treeview.heading(self, col, command='')
            if 'drag_cols' in kw:
                config = True
                drag_cols = bool(kw.pop('drag_cols'))
                if drag_cols != self._drag_cols:
                    self._drag_cols = drag_cols
                    if self._drag_cols:
                        self._im_drag.paste(self._im_draggable)
                    else:
                        self._im_drag.paste(self._im_not_draggable)
                    self.focus_set()
                    self.update_idletasks()
            if 'drag_rows' in kw:
                config = True
                self._drag_rows = bool(kw.pop('drag_rows'))
            if 'columns' in kw:
                for col in list(self._column_types.keys()):
                    if col not in kw['columns']:
                        del self._column_types[col]
                for col in kw['columns']:
                    if col not in self._column_types:
                        self._column_types[col] = str

            kw2 = kw.copy()
            kw2.pop('displaycolumns', None)
            kw2.pop('xscrollcommand', None)
            kw2.pop('yscrollcommand', None)
            if isinstance(cnf, dict):
                cnf2 = cnf.copy()
                cnf2.pop('displaycolumns', None)
                cnf2.pop('xscrollcommand', None)
                cnf2.pop('yscrollcommand', None)
            else:
                cnf2 = cnf
            self._visual_drag.configure(cnf2, **kw2)
            if kw or not config:
                return ttk.Treeview.configure(self, cnf, **kw)

    def delete(self, *items):
        self._visual_drag.delete(*items)
        ttk.Treeview.delete(self, *items)

    def detach(self, *items):
        self._visual_drag.detach(*items)
        ttk.Treeview.detach(self, *items)

    def heading(self, column, option=None, **kw):
        if kw and not kw.get('image'):
            kw['image'] = self._im_drag
        if kw:
            self._visual_drag.heading(ttk.Treeview.column(self, column, 'id'), option, **kw)
        return ttk.Treeview.heading(self, column, option, **kw)

    def insert(self, parent, index, iid=None, **kw):
        self._visual_drag.insert(parent, index, iid, **kw)
        return ttk.Treeview.insert(self, parent, index, iid, **kw)

    def item(self, item, option=None, **kw):
        if kw:
            self._visual_drag.item(item, option, **kw)
        return ttk.Treeview.item(self, item, option, **kw)

    def keys(self):
        keys = list(ttk.Treeview.keys(self))
        return keys + ['sortable', 'drag_cols']

    def move(self, item, parent, index):
        self._visual_drag.move(item, parent, index)
        ttk.Treeview.move(self, item, parent, index)

    def reattach(self, item, parent, index):
        self._visual_drag.reattach(item, parent, index)
        ttk.Treeview.reattach(self, item, parent, index)

    def set(self, item, column=None, value=None):
        if value is not None:
            self._visual_drag.set(item, ttk.Treeview.column(self, column, 'id'), value)
        return ttk.Treeview.set(self, item, column, value)

    def set_children(self, item, *newchildren):
        self._visual_drag.set_children(item, *newchildren)
        ttk.Treeview.set_children(self, item, *newchildren)