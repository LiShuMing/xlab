package com.starrocks.itest.framework.conf

import com.fasterxml.jackson.annotation.JsonProperty
import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory
import com.fasterxml.jackson.module.kotlin.KotlinModule
import com.fasterxml.jackson.module.kotlin.MissingKotlinParameterException
import java.nio.file.Files
import java.nio.file.Path

data class MysqlClient(@JsonProperty("host") val host: String = "",
                       @JsonProperty("port") val port: String = "",
                       @JsonProperty("user") val user: String = "",
                       @JsonProperty("password") val password: String = "",
                       @JsonProperty("http_port") val httpPort: String = "")

data class Env(@JsonProperty("oss_bucket") val ossBucket: String = "",
               @JsonProperty("hdfs_host") val hdfsHost: String = "",
               @JsonProperty("hdfs_port") val hdfsPort: String = "",
               @JsonProperty("hdfs_user") val hdfsUser: String = "",
               @JsonProperty("hdfs_passwd") val hdfsPasswd: String = "",
               @JsonProperty("hdfs_path") val hdfsPath: String = "",
               @JsonProperty("hdfs_broker_name") val hdfsBrokerName: String = "",
               @JsonProperty("hive_metastore_uris") val hiveMetastoreUris: String = "",
               @JsonProperty("hudi_hive_metastore_uris") val hudiMetastoreUris: String = "",
               @JsonProperty("iceberg_catalog_hive_metastore_uris") val icebergMetaStoreUris: String = "",
               @JsonProperty("external_mysql_ip") val externalMysqlIp: String = "",
               @JsonProperty("external_mysql_port") val externalMysqlPort: String = "",
               @JsonProperty("external_mysql_user") val externalMysqlUser: String = "",
               @JsonProperty("external_mysql_password") val externalMysqlPassword: String = "",
               @JsonProperty("jdbc_url") val jdbcUrl:String = "")

class SRConf(@JsonProperty("mysql-client") val mysqlClient: MysqlClient,
             @JsonProperty("env") val env: Env) {

    companion object {
        fun parse(path: Path): SRConf {

            val kotlinModule = KotlinModule.Builder().nullIsSameAsDefault(true).build()
            val mapper = ObjectMapper(YAMLFactory())
                .registerModules(kotlinModule)

            return try {
                Files.newBufferedReader(path).use {
                    mapper.readValue(it, SRConf::class.java)
                }
            } catch (exception: MissingKotlinParameterException) {
                throw exception
            }
        }
    }
}