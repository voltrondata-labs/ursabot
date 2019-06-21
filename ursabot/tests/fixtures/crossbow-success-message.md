[Builder1 (#{build_id})]({build_url}) builder {status}

Revision: {revision}

Submitted crossbow builds: [{repo} @ {branch}](https://github.com/{repo}/branches/all?query={branch})

|Task|Status|
|----|------|
|docker-cpp-cmake32|[![CircleCI Status](https://circleci.com/gh/{repo}/tree/{branch}-circle-docker-cpp-cmake32.svg?style=svg)](https://circleci.com/gh/{repo}/tree/{branch}-circle-docker-cpp-cmake32)|
|wheel-osx-cp37m|[![TravisCI Status](https://travis-ci.org/{repo}.svg?branch={branch}-travis-wheel-osx-cp37m)](https://travis-ci.org/{repo}/branches)|
|wheel-osx-cp36m|[![TravisCI Status](https://travis-ci.org/{repo}.svg?branch={branch}-travis-wheel-osx-cp36m)](https://travis-ci.org/{repo}/branches)|
|wheel-win-cp36m|[![Appveyor Status](https://ci.appveyor.com/api/projects/status/{appveyor_id}/branch/{branch}-appveyor-wheel-win-cp36m&svg=true)](https://ci.appveyor.com/project/{repo}/history)|
