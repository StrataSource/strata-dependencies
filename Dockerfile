FROM git.stratasource.org:5050/strata/ci/chaos-cas2-steamrt:latest

RUN apt-get update -y && apt-get install -y txt2man chrpath

#RUN apt-get install -y cargo

# HOME must be set to somewhere we have write access
RUN mkdir /myhome
ENV HOME=/myhome

# Hackjob of a rust install. cargo/rust provided by the package manager is way too old, so install it externally.
RUN curl https://sh.rustup.rs -sSf > install.sh && sh install.sh -y

# And of course we can't just throw it in /usr/local!
ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/myhome/.cargo/bin

RUN rustup +stable install && rustup default stable

# Yet another horrible hack! I'm not able to override the cc/cxx that the cargo-c/cc package uses, so I literally have to override the cc/cxx symlinks.
# Why would you ever want to respect CC/CXX environment vars, anyway?
# The current version of cc (gcc-15) does not have libgcc_s.so, only libgcc_s.a. Rust can't handle this for whatever reason. gcc-10 in our container *does* have this, though.
RUN cd /usr/bin; \
    rm cc; rm cxx; \
    ln -s gcc-10 cc; \
    ln -s g++-10 cxx;

# Finally we can install the single package we need.
RUN cargo install cargo-c

# Ugh
RUN chmod -R o+rwx /myhome
