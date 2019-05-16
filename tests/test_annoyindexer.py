import os
import shutil
import unittest

import numpy as np

from gnes.helper import touch_dir
from gnes.indexer.annoy import AnnoyIndexer


class TestFIndexer(unittest.TestCase):
    def setUp(self):
        self.toy_data = np.random.random([10, 5]).astype(np.float32)

        self.data_path = './test_bindexer_data'
        touch_dir(self.data_path)
        self.dump_path = os.path.join(self.data_path, 'indexer.pkl')

    def tearDown(self):
        if os.path.exists(self.data_path):
            shutil.rmtree(self.data_path)
            # os.remove(self.data_path)

    def test_search(self):
        a = AnnoyIndexer(5, self.data_path)
        a.add(list(range(10)), self.toy_data)
        self.assertEqual(a.size, 10)
        self.assertEqual(a.query(self.toy_data, top_k=1), [[(j, 0.0)] for j in range(10)])
        a.close()