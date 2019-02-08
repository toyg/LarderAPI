import os
from unittest import TestCase

from LarderAPI import Tag, init


class TestTag(TestCase):

    def setUp(self):
        init(os.getenv("token_test"))

    def test_create(self):
        # full constructor
        t = Tag(name=None, id=None, color=None, created=None, modified=None)
        name = "test_tag1"
        t.name = name
        t.save()
        self.assertIsNotNone(t.id)
        self.assertIsNotNone(t.created)
        self.assertIsNotNone(t.color)
        self.assertIsNotNone(t.modified)
        self.assertEqual(t.name, name)
        t.delete()

        # short version
        name2 = "test_tag2"
        t2 = Tag(name=name2)
        t2.save()
        self.assertIsNotNone(t2.id)
        self.assertEqual(t2.name, name2)
        t2.delete()

        # invalid attempt
        t3 = Tag()
        self.assertRaises(ValueError, t3.save)
        t3.created = "blah"
        self.assertRaises(ValueError, t3.save)
