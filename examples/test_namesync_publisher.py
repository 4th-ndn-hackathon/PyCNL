# -*- Mode:python; c-file-style:"gnu"; indent-tabs-mode:nil -*- */
#
# Copyright (C) 2014-2017 Regents of the University of California.
# Author: Jeff Thompson <jefft0@remap.ucla.edu>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# A copy of the GNU Lesser General Public License is in the file COPYING.

import time
import select
import sys
import glob
from pyndn import Name
from pyndn import Data
from pyndn import Face
from pyndn.security import KeyChain
from pyndn.util import MemoryContentCache
from pycnl import NameSyncHandler
from pycnl import Namespace

def dump(*list):
    result = ""
    for element in list:
        result += (element if type(element) is str else str(element)) + " "
    print(result)


def onRegisterFailed(prefix):
    dump("Register failed for prefix", prefix.toUri())

def promptAndInput(prompt):
    if sys.version_info[0] <= 2:
        return raw_input(prompt)
    else:
        return input(prompt)

def publishNewVersion(name,content,currVer,memcc,keyChain,namespace):
    data = Data(Name(name))
    data.getName().appendVersion(currVer)
    data.getName().appendSegment(0)
    data.getMetaInfo().setFinalBlockId(data.getName().get(-1))

    data.setContent(content)
    keyChain.sign(data, keyChain.getDefaultCertificateName())

    memcc.add(data)
    namespace.getChild(data.getName().getPrefix(-1))
    # dump("Sent content", content)
    print("Published "+str(data.getContent().size())+" bytes, name "+data.getName().toUri())
    

def main():
    currVer=1
    # name="/com/newspaper/sport/superbowl2017.html"
    name="/ndn/hackathon/cnl-demo/slides"
    usrPrefix = Name("/com/newspaper/USER/alice")
    # The default Face will connect using a Unix socket, or to "localhost".
    face = Face("memoria.ndn.ucla.edu")

    namespace = Namespace(name)
    namespace.setFace(face)
    # Use the system default key chain and certificate name to sign commands.
    keyChain = KeyChain()
    face.setCommandSigningInfo(keyChain, keyChain.getDefaultCertificateName())

    NameSyncHandler(namespace,usrPrefix,keyChain,keyChain.getDefaultCertificateName())

    # Also use the default certificate name to sign data packets.

    memcc=MemoryContentCache(face)
    prefix = Name("/com/newspaper")
    dump("Register prefix", prefix.toUri())
    memcc.registerPrefix(prefix, onRegisterFailed)

    folder = promptAndInput("Enter folder with images: ")
    imageFiles = glob.glob(folder+'/*.jpg')
    print("loaded "+str(len(imageFiles))+" images")

    idx = 0
    run = True
#TODO catch ctrl-c
    while run:
        isReady, _, _ = select.select([sys.stdin], [], [], 0)
        if len(isReady) != 0:
            print('will publish image '+imageFiles[idx])
            promptAndInput("")
            with open(imageFiles[idx],"rb") as f:
                content = f.read(7500)
                publishNewVersion(name, content, idx+1, memcc, keyChain, namespace)
            idx += 1
            run = idx < len(imageFiles)

        face.processEvents()
        # We need to sleep for a few milliseconds so we don't use 100% of the CPU.
        time.sleep(0.01)

    face.shutdown()

main()
