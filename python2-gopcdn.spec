%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()"
)}

%define proj_name gopcdn

%define _release RELEASEVERSION

Name:           python-%{proj_name}
Version:        RPMVERSION
Release:        %{_release}%{?dist}
Summary:        simpleutil copy from openstack
Group:          Development/Libraries
License:        MPLv1.1 or GPLv2
URL:            http://github.com/Lolizeppelin/%{proj_name}
Source0:        %{proj_name}-%{version}.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch:      noarch

BuildRequires:  python-setuptools >= 11.0

Requires:       python >= 2.6.6
Requires:       python < 3.0
Requires:       python-goperation-application >= 1.0
Requires:       python-goperation-application < 1.1
Requires:       python-simpleservice-ormdb >= 1.0
Requires:       python-simpleservice-ormdb < 1.1

%description
utils for update cdn resource

%prep
%setup -q -n %{proj_name}-%{version}
rm -rf %{proj_name}.egg-info

%build
%{__python} setup.py build

%install
%{__rm} -rf %{buildroot}
%{__python} setup.py install -O1 --skip-build --root %{buildroot}

%clean
%{__rm} -rf %{buildroot}


%files
%defattr(-,root,root,-)
%{python_sitelib}/%{proj_name}/*
%{python_sitelib}/%{proj_name}-%{version}-*.egg-info/*
%dir %{python_sitelib}/%{proj_name}-%{version}-*.egg-info/
%doc README.rst
%doc doc/*

%changelog

* Mon Aug 29 2017 Lolizeppelin <lolizeppelin@gmail.com> - 1.0.0
- Initial Package