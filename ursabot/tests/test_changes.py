import re

from buildbot.test.fake.change import Change
from buildbot.test.unit import test_changes_filter as original

from ursabot.changes import ChangeFilter


class TestChangeFilter(original.ChangeFilter):

    def setfilter(self, **kwargs):
        self.filt = ChangeFilter(**kwargs)

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
