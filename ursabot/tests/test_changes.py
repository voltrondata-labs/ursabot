# This file is mostly a derivative work of Buildbot.
#
# Buildbot is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

import re

from buildbot.test.fake.change import Change as FakeChange
from buildbot.test.unit import test_changes_filter as original

from ursabot.changes import ChangeFilter
from ursabot.utils import Glob, AnyOf, AllOf


class Change(FakeChange):
    files = []


class TestChangeFilter(original.ChangeFilter):

    def setfilter(self, filter=None, **kwargs):
        if filter is None:
            self.filt = ChangeFilter(**kwargs)
        else:
            self.filt = filter

    def test_filter_change_filter_fn(self):
        self.setfilter(fn=lambda ch: ch.x > 3)
        self.no(Change(x=2), 'filter_fn returns False')
        self.yes(Change(x=4), 'filter_fn returns True')
        self.check()

    def test_filter_change_filt_re(self):
        self.setfilter(category=re.compile('^a.*'))
        self.yes(Change(category='albert'), 'matching CATEGORY returns True')
        self.no(Change(category='boris'),
                'non-matching CATEGORY returns False')
        self.check()

    def test_filter_change_branch_re(self):  # regression - see #927
        self.setfilter(branch=re.compile('^t.*'))
        self.yes(Change(branch='trunk'), 'matching BRANCH returns True')
        self.no(Change(branch='development'),
                'non-matching BRANCH returns False')
        self.no(Change(branch=None), 'branch=None returns False')
        self.check()

    def test_filter_change_filt_re_compiled(self):
        self.setfilter(category=re.compile('^b.*', re.I))
        self.no(Change(category='albert'),
                'non-matching CATEGORY returns False')
        self.yes(Change(category='boris'), 'matching CATEGORY returns True')
        self.yes(Change(category='Bruce'),
                 'matching CATEGORY returns True, using re.I')
        self.check()

    def test_filter_change_combination_filter_fn(self):
        self.setfilter(project='p', repository='r', branch='b', category='c',
                       fn=lambda c: c.ff)
        change = Change(project='x', repository='x', branch='x', category='x',
                        ff=False)
        self.no(change, 'none match and fn returns False -> False')

        change = Change(project='p', repository='r', branch='b', category='c',
                        ff=False)
        self.no(change, 'all match and fn returns False -> False')

        change = Change(project='x', repository='x', branch='x', category='x',
                        ff=True)
        self.no(change, 'none match and fn returns True -> False')

        change = Change(project='p', repository='r', branch='b', category='c',
                        ff=True)
        self.yes(change, 'all match and fn returns True -> False')
        self.check()

    def test_filter_props(self):
        self.setfilter(properties={
            'event.type': 'ref-updated'
        })
        self.yes(Change(properties={'event.type': 'ref-updated'}),
                 'matching property')
        self.no(Change(properties={'event.type': 'patch-uploaded'}),
                'non matching property')
        self.no(Change(properties={}),
                'no property')
        self.check()

    def test_filter_props_fn(self):
        self.setfilter(properties={
            'event.type': lambda v: v.startswith('ref')
        })
        self.yes(Change(properties={'event.type': 'ref-updated'}),
                 'matching property')
        self.no(Change(properties={'event.type': 'patch-uploaded'}),
                'non matching property')
        self.no(Change(properties={}),
                'no property')
        self.check()

    def test_filter_files(self):
        rust_change = Change(files=[
            'rust/src/something.rs'
        ])
        java_change = Change(files=[
            'java/vector/src/main/Something.java'
            'java/vector/src/test/TestSomething.java'
        ])
        cpp_change = Change(files=[
            'cpp/src/something.cc'
            'cpp/src/something.h'
        ])
        python_change = Change(files=[
            'python/module.py',
            'python/tests/module.py'
        ])

        self.setfilter(files=Glob('rust/*'))
        self.yes(rust_change, 'rust change matches rust pattern')
        self.no(java_change, 'java change not matches rust pattern')
        self.no(cpp_change, 'cpp change not matches rust pattern')
        self.no(python_change, 'python change not matches rust pattern')
        self.check()

        self.setfilter(files=Glob('cpp/*'))
        self.no(rust_change, 'rust change not matches cpp pattern')
        self.no(java_change, 'java change not matches cpp pattern')
        self.yes(cpp_change, 'cpp change matches cpp pattern')
        self.no(python_change, 'python change not matches rust pattern')
        self.check()

        self.setfilter(files=AnyOf(Glob('cpp/*'), Glob('python/*')))
        self.no(rust_change, 'rust change not matches python pattern')
        self.no(java_change, 'java change not matches python pattern')
        self.yes(cpp_change, 'cpp change matches python pattern')
        self.yes(python_change, 'python change matches python pattern')
        self.check()

        self.setfilter(files=AnyOf(
            Glob('cpp/*'),
            Glob('python/*'),
            Glob('java/*'),
            Glob('rust/*')
        ))
        self.yes(rust_change, 'rust change matches integration pattern')
        self.yes(java_change, 'java change matches integration pattern')
        self.yes(cpp_change, 'cpp change matches integration pattern')
        self.yes(python_change, 'python change matches integration pattern')
        self.check()

    def test_filter_or_combining(self):
        filter_a = ChangeFilter(
            project='a',
            category=AnyOf(None, 'tag', 'pull'),
        )
        filter_b = ChangeFilter(
            project='b',
            category='pull',
        )
        either = ChangeFilter(AnyOf(filter_a, filter_b))

        self.setfilter(either)
        self.yes(Change(project='a', category='tag'), 'on tag of project a')
        self.yes(Change(project='b', category='pull'), 'on pull of project b')
        self.no(Change(project='b', category='tag'),
                'not on tag of project b')
        self.no(Change(project='a', category='comment'),
                'not on comment of project a')
        self.check()

    def test_filter_and_combining(self):
        filter_a = ChangeFilter(
            project='a',
            category=AnyOf(None, 'tag', 'pull'),
        )
        filter_b = ChangeFilter(
            files=Glob('cpp/*')
        )
        both = ChangeFilter(AllOf(filter_a, filter_b))

        self.setfilter(both)
        self.yes(
            Change(project='a', category='tag', files=['cpp/test.cc']),
            'on tag of project a with cc file'
        )
        self.yes(
            Change(project='a', category='tag', files=[
                'python/setup.py',
                'cpp/test.cc'
            ]),
            'on tag of project a with both cc and python files'
        )
        self.no(
            Change(project='a', category='tag', files=[
                'rust/test.rs',
                'java/test.java'
            ]),
            'not on tag of project a with non matching file'
        )
        self.no(
            Change(project='a', category='tag', files=[]),
            'on tag of project a without files'
        )
        self.check()
