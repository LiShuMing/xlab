#!/usr/bin/perl
use strict;
use warnings;
use Data::Dumper;

my %colsFiles = map{$_=~/(\w+)\.col/;($1,$_)} map{chomp;$_} qx(ls *.cols);
my %sqlFiles = map{$_=~/(\w+)\.sql/;($1,$_)} map{chomp;$_} qx(ls *.sql);
print Dumper(\%colsFiles, \%sqlFiles);

die "no available files" unless scalar(%colsFiles) > 0 and scalar(%sqlFiles) > 0 and scalar(%colsFiles) == scalar(%sqlFiles);

my @keys = keys %colsFiles;
my @matchedKeys = grep {exists $sqlFiles{$_} } keys %colsFiles;
die "not matched" unless scalar(@matchedKeys) == scalar(@keys);

foreach my $t (keys %colsFiles) {
  open my $fh, "> $t.broker_load.properties" or die "Can't open file :$!";
  printf $fh qq/brokerLoad.table=$t\n/;
  printf $fh qq/brokerLoad.format=csv\n/;
  my ($cols) = map {chomp;$_} qx(cat $colsFiles{$t});
  printf $fh qq/brokerLoad.columns=$cols\n/;
  printf $fh qq/brokerLoad.columnSeparator=|\n/;
  printf $fh qq{brokerLoad.hdfsPath=/starrocks/test_data/tpcds_1g/$t.dat\n};
  close $fh;
}
