#  Tencent is pleased to support the open source community by making GNES available.
#
#  Copyright (C) 2019 THL A29 Limited, a Tencent company. All rights reserved.
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
import io
from typing import List

from PIL import Image
import imagehash
from .base import BaseVideoPreprocessor
from ...proto import gnes_pb2, array2blob
import subprocess as sp


class FfmpegPreprocessor(BaseVideoPreprocessor):

    def __init__(self,
                 duplicate_rm=True,
                 use_phash_weight=False,
                 phash_thresh=5,
                 *args, **kwargs):

        # (-i, -) input from stdin pipeline
        # (-f, image2pipe) output format is image pipeline
        self.cmd = ['ffmpeg',
                    '-i', '-',
                    '-f', 'image2pipe']

        # example k,v pair:
        #    (-s, 420*360)
        #    (-vsync, vfr)
        #    (-vf, select=eq(pict_type\,I))
        for k, v in kwargs.items():
            self.cmd.append('-' + k)
            self.cmd.append(v)

        # (-c:v, png) output bytes in png format
        # (-) output to stdout pipeline
        self.cmd += ['-c:v', 'png', '-']
        self.phash_thresh = phash_thresh

    def apply(self, doc: 'gnes_pb2.Document'):
        super().apply(doc)

        # video could't be processed from ndarray!
        # only bytes can be passed into ffmpeg pipeline
        if doc.raw_bytes:
            pipe = sp.Popen(self.cmd, stdin=sp.PIPE, stdout=sp.PIPE, bufsize=-1)
            stream, _ = pipe.communicate(doc.raw_bytes)
            stream = stream.split(b'\x89PNG')
            if len(stream <= 1):
                self.logger.error('video stream error, no image extracted')
                return
            stream = [b'\x89PNG' + _ for _ in stream[1:]]

            # remove dupliated key frames by phash value
            if self.duplicate_rm:
                stream = self.duplicate_rm(stream)
            for ci, chunk in enumerate(stream):
                c = doc.chunks.add()
                c.doc_id = doc.doc_id
                c.blob.CopyFrom(array2blob(chunk))
                c.offset_1d = ci
                c.weight = 1 / len(stream)
        else:
            self.logger.error('bad document: "raw_bytes" is empty!')

    def phash(self, image_bytes: bytes):
        return imagehash.phash(Image.open(io.BytesIO(image_bytes)))

    def duplicate_rm(self, image_list: List[bytes]):
        hash_list = [self.phash(_) for _ in image_list]
        ret = []
        for i, h in enumerate(hash_list):
            flag = 1
            if len(ret) >= 1:
                # only keep images with high phash diff
                # speed improve by comparing last 9 pics
                for j in range(1, min(len(ret)+1, 9)):
                    dist = abs(ret[-j][1] - h)
                    if dist < self.phash_thresh:
                        flag = 0
                        break
            if flag:
                ret.append(i)
        return [image_list[_] for _ in ret]
