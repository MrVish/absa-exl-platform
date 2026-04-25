resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-rt-public"
  })
}

resource "aws_route_table_association" "public" {
  count = var.availability_zones

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  count = var.availability_zones

  vpc_id = aws_vpc.this.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this[local.is_prod ? count.index : 0].id
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-rt-private-${count.index}"
  })
}

resource "aws_route_table_association" "private" {
  count = var.availability_zones

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

resource "aws_route_table" "data" {
  vpc_id = aws_vpc.this.id

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-rt-data"
  })
}

resource "aws_route_table_association" "data" {
  count = var.availability_zones

  subnet_id      = aws_subnet.data[count.index].id
  route_table_id = aws_route_table.data.id
}
